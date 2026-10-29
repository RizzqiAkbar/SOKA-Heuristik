package org.example;

import org.cloudsimplus.allocationpolicies.VmAllocationPolicySimple;
import org.cloudsimplus.brokers.DatacenterBroker;
import org.cloudsimplus.brokers.DatacenterBrokerSimple;
import org.cloudsimplus.cloudlets.Cloudlet;
import org.cloudsimplus.cloudlets.CloudletSimple;
import org.cloudsimplus.core.CloudSimPlus;
import org.cloudsimplus.datacenters.Datacenter;
import org.cloudsimplus.datacenters.DatacenterSimple;
import org.cloudsimplus.hosts.Host;
import org.cloudsimplus.hosts.HostSimple;
import org.cloudsimplus.resources.Pe;
import org.cloudsimplus.resources.PeSimple;
import org.cloudsimplus.schedulers.cloudlet.CloudletSchedulerSpaceShared;
import org.cloudsimplus.schedulers.vm.VmSchedulerTimeShared;
import org.cloudsimplus.utilizationmodels.UtilizationModelDynamic;
import org.cloudsimplus.vms.Vm;
import org.cloudsimplus.vms.VmSimple;

import java.io.BufferedReader;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Simulasi perbandingan algoritma (Max-Min, Min-Min, FCFS) dengan
 * 3 Datacenter, 5 Host, dan 2 VM menggunakan dataset GoCJ.
 */
public class Main {

    private static final int DC_COUNT = 3;      // jumlah datacenter
    private static final int HOST_PER_DC = 5;   // host per datacenter
    private static final int VM_PER_HOST = 2;
    private static final int HOST_COUNT = DC_COUNT * HOST_PER_DC;
    private static final int VM_COUNT = HOST_COUNT * VM_PER_HOST;
    private static final int VM_PER_DC = HOST_PER_DC * VM_PER_HOST;
    private static final int[] TASK_SCENARIOS = buildScenarios();
    private static final String[] ALGORITHMS = {"Max-Min", "Min-Min", "FCFS"};

    private static int[] buildScenarios() {
        List<Integer> list = new ArrayList<>();
        for (int n = 100; n <= 1000; n += 50) {
            if (Main.class.getResource("/dataset/GoCJ_Dataset_" + n + ".txt") != null) {
                list.add(n);
            }
        }
        if (list.isEmpty()) {
            return new int[]{100, 200, 500, 1000};
        }
        return list.stream().mapToInt(Integer::intValue).toArray();
    }

    private static final long HOST_SEED = 42;
    private static final long VM_SEED = 99;

    private static final double COST_PER_MIPS_SEC = 0.00001;
    private static final double GAP_WARN_RATIO = 0.01;

    private static final List<String> csvRows = new ArrayList<>();
    private static boolean allocationPrinted = false;
    private static final Map<Long, Host> vmHost = new TreeMap<>();
    private static final Map<Host, Datacenter> hostDatacenter = new IdentityHashMap<>();
    private static final Map<Datacenter, String> dcLabel = new IdentityHashMap<>();

    private static class ScheduleResult {
        final Map<Cloudlet, Vm> assignment;
        final List<Cloudlet> order;
        final double predictedMakespan;

        ScheduleResult(Map<Cloudlet, Vm> assignment, List<Cloudlet> order, double predictedMakespan) {
            this.assignment = assignment;
            this.order = order;
            this.predictedMakespan = predictedMakespan;
        }
    }

    public static void main(String[] args) throws IOException {
        String outDir = "output";
        Files.createDirectories(Paths.get(outDir));

        PrintStream terminal = System.out;
        try (PrintStream fileOut = new PrintStream(new FileOutputStream(outDir + "/output_terminal.txt"), false, StandardCharsets.UTF_8)) {
            System.setOut(new PrintStream(new TeeOutputStream(fileOut, terminal), true));
            csvRows.add("Algoritma,N_Task,Prediksi_Makespan,Makespan_Aktual,Gap_Persen,Throughput,Utilization_Persen,Imbalance,Total_Cost");
            for (String algo : ALGORITHMS) {
                for (int taskCount : TASK_SCENARIOS) {
                    runScenario(algo, taskCount);
                }
            }
        } finally {
            System.setOut(terminal);
        }
        writeCsv(outDir + "/hasil_metrik_perbandingan.csv");
    }

    private static void runScenario(String algorithm, int taskCount) {
        CloudSimPlus simulation = new CloudSimPlus();

        List<Host> hostList = createHosts();

        List<Datacenter> datacenters = new ArrayList<>();
        hostDatacenter.clear();
        dcLabel.clear();
        for (int d = 0; d < DC_COUNT; d++) {
            List<Host> dcHosts = new ArrayList<>(hostList.subList(d * HOST_PER_DC, (d + 1) * HOST_PER_DC));
            Datacenter dc = new DatacenterSimple(simulation, dcHosts, new VmAllocationPolicySimple());
            datacenters.add(dc);
            dcLabel.put(dc, "DC" + (d + 1));
            for (Host h : dcHosts) hostDatacenter.put(h, dc);
        }

        List<Vm> vmList = createVms();

        DatacenterBroker broker = new DatacenterBrokerSimple(simulation);

        // Distribusikan VM ke datacenter secara berurutan: VM_PER_DC VM per DC
        broker.setDatacenterMapper((defaultDc, vm) ->
                datacenters.get((int) Math.min(vm.getId() / VM_PER_DC, DC_COUNT - 1)));
        broker.submitVmList(vmList);

        List<Cloudlet> cloudletList = loadGoCJDataset(taskCount);

        ScheduleResult sr = switch (algorithm) {
            case "Max-Min" -> maxMinSchedule(cloudletList, vmList);
            case "Min-Min" -> minMinSchedule(cloudletList, vmList);
            case "FCFS" -> fcfsSchedule(cloudletList, vmList);
            default -> throw new IllegalArgumentException(algorithm);
        };

        for (Cloudlet c : cloudletList) {
            broker.bindCloudletToVm(c, sr.assignment.get(c));
        }
        broker.submitCloudletList(sr.order);

        vmHost.clear();
        for (Vm vm : vmList) {
            vm.addOnHostAllocationListener(e -> vmHost.put(e.getVm().getId(), e.getHost()));
        }

        simulation.start();

        printVmHostAllocation(hostList, vmList, datacenters);
        printMetrics(algorithm, taskCount, broker, vmList, sr.predictedMakespan);
    }

    private static void printVmHostAllocation(List<Host> hostList, List<Vm> vmList, List<Datacenter> datacenters) {
        if (allocationPrinted) return;
        allocationPrinted = true;

        System.out.println("\n================== STRUKTUR & ALOKASI INFRASTRUKTUR ==================");
        System.out.println("Total Datacenter: " + datacenters.size() + ", Total Host: " + hostList.size() + ", Total VM: " + vmList.size());

        for (int i = 0; i < datacenters.size(); i++) {
            System.out.printf("Datacenter %d (ID: %d) memiliki %d host%n",
                    (i + 1), datacenters.get(i).getId(), datacenters.get(i).getHostList().size());
        }

        System.out.println("\n-- Detail Pemetaan VM -> Host -> Datacenter --");
        for (Vm vm : vmList) {
            Host h = vmHost.get(vm.getId());
            if (h == null) {
                System.out.printf("VM %-2d : TIDAK tercatat%n", vm.getId());
                continue;
            }
            Datacenter dc = hostDatacenter.get(h);
            System.out.printf("VM %-2d -> MIPS: %-4d, PEs: %d, RAM: %-4d MB | Berjalan di Host %-2d -> %s%n",
                    vm.getId(), (long) vm.getMips(), vm.getPesNumber(), vm.getRam().getCapacity(),
                    h.getId(), dcLabel.getOrDefault(dc, "DC?"));
        }
        System.out.println("=======================================================================\n");
    }

    private static List<Host> createHosts() {
        List<Host> hostList = new ArrayList<>();
        Random rand = new Random(HOST_SEED);
        for (int i = 0; i < HOST_COUNT; i++) {
            int peCount = 4 + rand.nextInt(13);
            long mipsPerPe = 1000 + rand.nextInt(2001);
            long ram = 4096 + rand.nextInt(12289);
            List<Pe> peList = new ArrayList<>();
            for (int p = 0; p < peCount; p++) peList.add(new PeSimple(mipsPerPe));
            Host host = new HostSimple(ram, 10_000, 1_000_000, peList);
            host.setVmScheduler(new VmSchedulerTimeShared());
            hostList.add(host);
        }
        return hostList;
    }

    private static List<Vm> createVms() {
        List<Vm> vmList = new ArrayList<>();
        Random rand = new Random(VM_SEED);
        for (int i = 0; i < VM_COUNT; i++) {
            long mips = 250 + rand.nextInt(751);
            int pes = 1 + rand.nextInt(4);
            long ram = 512 + rand.nextInt(1537);
            Vm vm = new VmSimple(mips, pes);
            vm.setRam(ram).setBw(1_000).setSize(10_000);
            vm.setCloudletScheduler(new CloudletSchedulerSpaceShared());
            vmList.add(vm);
        }
        return vmList;
    }

    private static List<Cloudlet> loadGoCJDataset(int n) {
        String path = "/dataset/GoCJ_Dataset_" + n + ".txt";
        List<Long> lengths = new ArrayList<>();
        try (InputStream is = Main.class.getResourceAsStream(path)) {
            if (is == null) {
                throw new RuntimeException("File dataset tidak ditemukan di classpath: " + path);
            }
            BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (!line.isEmpty()) lengths.add(Long.parseLong(line));
            }
        } catch (IOException e) {
            throw new RuntimeException("Gagal membaca " + path, e);
        }
        List<Cloudlet> list = new ArrayList<>();
        for (long length : lengths) {
            Cloudlet cloudlet = new CloudletSimple(length, 1);
            cloudlet.setFileSize(300).setOutputSize(300);
            cloudlet.setUtilizationModelCpu(new UtilizationModelDynamic(1.0));
            list.add(cloudlet);
        }
        return list;
    }

    private static int fastestPe(double[][] avail, int vmIdx) {
        int best = 0;
        for (int p = 1; p < avail[vmIdx].length; p++) {
            if (avail[vmIdx][p] < avail[vmIdx][best]) best = p;
        }
        return best;
    }

    private static ScheduleResult maxMinSchedule(List<Cloudlet> cloudlets, List<Vm> vms) {
        return minMaxGeneric(cloudlets, vms, true);
    }

    private static ScheduleResult minMinSchedule(List<Cloudlet> cloudlets, List<Vm> vms) {
        return minMaxGeneric(cloudlets, vms, false);
    }

    private static ScheduleResult minMaxGeneric(List<Cloudlet> cloudlets, List<Vm> vms, boolean pickMax) {
        Map<Cloudlet, Vm> result = new IdentityHashMap<>();
        List<Cloudlet> order = new ArrayList<>();
        double[][] avail = new double[vms.size()][];
        for (int j = 0; j < vms.size(); j++) avail[j] = new double[(int) vms.get(j).getPesNumber()];

        List<Cloudlet> remaining = new ArrayList<>(cloudlets);
        while (!remaining.isEmpty()) {
            double bestOfBest = pickMax ? -1 : Double.MAX_VALUE;
            int bestTaskIdx = -1, bestVmIdx = -1, bestPeIdx = -1;

            for (int i = 0; i < remaining.size(); i++) {
                Cloudlet c = remaining.get(i);
                double minCompletion = Double.MAX_VALUE;
                int minVmIdx = -1, minPeIdx = -1;
                for (int j = 0; j < vms.size(); j++) {
                    int p = fastestPe(avail, j);
                    double completion = avail[j][p] + c.getLength() / vms.get(j).getMips();
                    if (completion < minCompletion) {
                        minCompletion = completion;
                        minVmIdx = j;
                        minPeIdx = p;
                    }
                }
                boolean better = pickMax ? (minCompletion > bestOfBest) : (minCompletion < bestOfBest);
                if (better) {
                    bestOfBest = minCompletion;
                    bestTaskIdx = i;
                    bestVmIdx = minVmIdx;
                    bestPeIdx = minPeIdx;
                }
            }

            Cloudlet chosen = remaining.remove(bestTaskIdx);
            Vm chosenVm = vms.get(bestVmIdx);
            result.put(chosen, chosenVm);
            order.add(chosen);
            avail[bestVmIdx][bestPeIdx] += chosen.getLength() / chosenVm.getMips();
        }

        double predicted = 0;
        for (double[] row : avail) for (double t : row) predicted = Math.max(predicted, t);
        return new ScheduleResult(result, order, predicted);
    }

    private static ScheduleResult fcfsSchedule(List<Cloudlet> cloudlets, List<Vm> vms) {
        Map<Cloudlet, Vm> result = new IdentityHashMap<>();
        List<Cloudlet> order = new ArrayList<>();
        double[][] avail = new double[vms.size()][];
        for (int j = 0; j < vms.size(); j++) avail[j] = new double[(int) vms.get(j).getPesNumber()];

        for (Cloudlet c : cloudlets) {
            int bestVmIdx = -1, bestPeIdx = -1;
            double bestT = Double.MAX_VALUE;
            for (int j = 0; j < vms.size(); j++) {
                int p = fastestPe(avail, j);
                if (avail[j][p] < bestT) {
                    bestT = avail[j][p];
                    bestVmIdx = j;
                    bestPeIdx = p;
                }
            }
            Vm chosenVm = vms.get(bestVmIdx);
            avail[bestVmIdx][bestPeIdx] += c.getLength() / chosenVm.getMips();
            result.put(c, chosenVm);
            order.add(c);
        }

        double predicted = 0;
        for (double[] row : avail) for (double t : row) predicted = Math.max(predicted, t);
        return new ScheduleResult(result, order, predicted);
    }

    private static void printMetrics(String algorithm, int taskCount, DatacenterBroker broker, List<Vm> vmList, double predictedMakespan) {
        List<Cloudlet> finished = broker.getCloudletFinishedList();

        double makespan = finished.stream().mapToDouble(Cloudlet::getFinishTime).max().orElse(0);
        double throughput = makespan > 0 ? finished.size() / makespan : 0;

        Map<Vm, Double> vmFinish = new IdentityHashMap<>();
        Map<Vm, Double> vmBusy = new IdentityHashMap<>();
        for (Cloudlet c : finished) {
            Vm vm = c.getVm();
            vmFinish.merge(vm, c.getFinishTime(), Math::max);
            vmBusy.merge(vm, (double) c.getLength() / vm.getMips(), Double::sum);
        }

        double[] finishTimes = new double[vmList.size()];
        double utilSum = 0;
        double totalCost = 0;
        for (int j = 0; j < vmList.size(); j++) {
            Vm vm = vmList.get(j);
            double finishJ = vmFinish.getOrDefault(vm, 0.0);
            double busyJ = vmBusy.getOrDefault(vm, 0.0);
            finishTimes[j] = finishJ;
            if (makespan > 0) utilSum += busyJ / (vm.getPesNumber() * makespan);
            totalCost += finishJ * vm.getMips() * vm.getPesNumber() * COST_PER_MIPS_SEC;
        }
        double avgUtilPct = 100.0 * utilSum / vmList.size();

        double mean = Arrays.stream(finishTimes).average().orElse(0);
        double variance = Arrays.stream(finishTimes).map(t -> (t - mean) * (t - mean)).average().orElse(0);
        double degreeOfImbalance = Math.sqrt(variance);

        double gap = predictedMakespan > 0 ? Math.abs(makespan - predictedMakespan) / predictedMakespan : 0;

        System.out.println("\n=== METRIK HASIL SIMULASI (" + algorithm + ", GoCJ) — N_Task=" + taskCount + " ===");
        System.out.printf("Task selesai / diharapkan   : %d / %d%n", finished.size(), taskCount);
        System.out.printf("Prediksi makespan (model)   : %.2f detik%n", predictedMakespan);
        System.out.printf("Makespan aktual (simulasi)  : %.2f detik  (selisih %.2f%%)%n", makespan, gap * 100);
        System.out.printf("Throughput                  : %.4f task/detik%n", throughput);

        // Detail Penggunaan VM & Datacenter
        System.out.println("\n-- Detail Penggunaan VM & Alokasi Datacenter --");
        Map<Vm, Long> taskCountPerVm = finished.stream().collect(Collectors.groupingBy(Cloudlet::getVm, Collectors.counting()));
        for (Vm vm : vmList) {
            long count = taskCountPerVm.getOrDefault(vm, 0L);
            Host h = vmHost.get(vm.getId());
            Datacenter dc = h != null ? hostDatacenter.get(h) : null;
            double busyJ = vmBusy.getOrDefault(vm, 0.0);
            double utilJ = makespan > 0 ? (busyJ / (vm.getPesNumber() * makespan)) * 100 : 0;
            System.out.printf("VM %d -> %s | Host ID: %d | MIPS: %-4d | PEs: %d | Task Selesai: %-4d | Utilisasi: %.2f%% | Finish Time: %.2fs%n",
                    vm.getId(),
                    dcLabel.getOrDefault(dc, "DC?"),
                    h != null ? h.getId() : -1,
                    (long) vm.getMips(),
                    vm.getPesNumber(),
                    count,
                    utilJ,
                    vmFinish.getOrDefault(vm, 0.0));
        }

        csvRows.add(String.format(Locale.US, "%s,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f",
                algorithm, taskCount, predictedMakespan, makespan, gap * 100, throughput, avgUtilPct, degreeOfImbalance, totalCost));
    }

    private static class TeeOutputStream extends OutputStream {
        private final OutputStream a, b;
        TeeOutputStream(OutputStream a, OutputStream b) { this.a = a; this.b = b; }
        public void write(int x) throws IOException { a.write(x); b.write(x); }
        public void flush() throws IOException { a.flush(); b.flush(); }
        public void close() throws IOException { try { a.close(); } finally { b.close(); } }
    }

    private static void writeCsv(String filename) {
        try {
            Files.write(Paths.get(filename), String.join("\n", csvRows).getBytes(StandardCharsets.UTF_8));
            System.out.println("\nCSV ditulis ke: " + filename);
        } catch (IOException e) {
            System.out.println("Gagal menulis CSV: " + e.getMessage());
        }
    }

}
