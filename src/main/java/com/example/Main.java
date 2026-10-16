package com.example;

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
import org.cloudsimplus.util.Log;
import ch.qos.logback.classic.Level;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

public class Main {

    private static final int DATACENTER_COUNT = 3;
    private static final int HOST_COUNT = 5; // host per datacenter
    private static final int VM_COUNT = 10;
    private static final int[] TASK_SCENARIOS = buildScenarios();
    private static final String[] ALGORITHMS = { "Max-Min", "Min-Min", "FCFS" };

    private static int[] buildScenarios() {
        int[] arr = new int[19];
        for (int i = 0; i < arr.length; i++) {
            arr[i] = 100 + i * 50;
        }
        return arr;
    }

    private static final long HOST_SEED = 42;
    private static final long VM_SEED = 99;

    private static final double COST_PER_MIPS_SEC = 0.00001;
    private static final List<String> csvRows = new ArrayList<>();

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

    public static void main(String[] args) {
        // Matikan log verbose internal dari CloudSim Plus agar terminal bersih
        Log.setLevel(Level.OFF);

        csvRows.add(
                "Algoritma,N_Task,Prediksi_Makespan,Makespan_Aktual,Gap_Persen,Throughput,Utilization_Persen,Imbalance,Total_Cost");

        // 1) Laporan infrastruktur: datacenter -> host -> VM
        printInfrastructureAllocation();

        // 2) Hasil simulasi per algoritma dan jumlah task
        System.out.println("\n=================== HASIL SIMULASI ===================");
        System.out.printf("%-10s | %-6s | %-13s | %-13s | %-8s | %-10s | %-9s | %-10s | %-10s%n",
                "Algoritma", "Tasks", "Prediksi (s)", "Aktual (s)", "Gap (%)",
                "Throughput", "Util (%)", "Imbalance", "Cost");
        System.out.println("-".repeat(115));

        for (String algo : ALGORITHMS) {
            for (int taskCount : TASK_SCENARIOS) {
                runScenario(algo, taskCount);
            }
            System.out.println("-".repeat(115));
        }

        writeCsv("hasil_metrik_perbandingan.csv");
    }

    // ------------------------------------------------------------------
    // Pembuatan datacenter (dipakai simulasi DAN laporan alokasi)
    // ------------------------------------------------------------------
    private static List<Datacenter> createDatacenters(CloudSimPlus simulation) {
        List<Datacenter> dcList = new ArrayList<>();
        for (int i = 0; i < DATACENTER_COUNT; i++) {
            // Ganti HOST_SEED dengan (HOST_SEED + i) jika ingin spesifikasi host tiap DC
            // berbeda
            dcList.add(new DatacenterSimple(simulation, createHosts(HOST_SEED), new VmAllocationPolicySimple()));
        }
        return dcList;
    }

    // Broker menyebar VM secara round-robin ke seluruh datacenter
    private static DatacenterBroker createBroker(CloudSimPlus simulation, List<Datacenter> dcList) {
        DatacenterBroker broker = new DatacenterBrokerSimple(simulation);
        int[] counter = { 0 };
        broker.setDatacenterMapper((lastDc, vm) -> dcList.get(counter[0]++ % dcList.size()));
        return broker;
    }

    // ------------------------------------------------------------------
    // Laporan alokasi: Datacenter -> Host -> VM
    // ------------------------------------------------------------------
    private static void printInfrastructureAllocation() {
        CloudSimPlus sim = new CloudSimPlus();
        List<Datacenter> dcList = createDatacenters(sim);
        List<Vm> vmList = createVms();

        // Tangkap host tempat tiap VM dialokasikan
        Map<Vm, Host> vmToHost = new IdentityHashMap<>();
        for (Vm vm : vmList) {
            vm.addOnHostAllocationListener(evt -> vmToHost.put(evt.getVm(), evt.getHost()));
        }

        DatacenterBroker broker = createBroker(sim, dcList);
        broker.submitVmList(vmList);
        sim.start();

        System.out.println("\n=================== INFRASTRUKTUR & ALOKASI ===================");
        System.out.println("Jumlah Datacenter : " + dcList.size());
        System.out.println("Host per DC       : " + HOST_COUNT);
        System.out.println("Total Host        : " + (dcList.size() * HOST_COUNT));
        System.out.println("Total VM          : " + vmList.size());

        Set<Vm> allocated = Collections.newSetFromMap(new IdentityHashMap<>());

        for (int d = 0; d < dcList.size(); d++) {
            Datacenter dc = dcList.get(d);
            List<? extends Host> hosts = dc.getHostList();

            int vmInDc = 0;
            for (Host host : hosts) {
                for (Vm vm : vmList) {
                    if (vmToHost.get(vm) == host)
                        vmInDc++;
                }
            }

            System.out.printf("%n[DATACENTER %d] (ID: %d) | Host: %d | Total VM: %d%n",
                    d + 1, dc.getId(), hosts.size(), vmInDc);

            for (int h = 0; h < hosts.size(); h++) {
                Host host = hosts.get(h);
                System.out.printf("  Host %d (ID: %d | PEs: %d | MIPS/PE: %.0f | RAM: %d MB)%n",
                        h + 1, host.getId(), host.getPesNumber(), host.getMips(),
                        host.getRam().getCapacity());

                boolean any = false;
                for (Vm vm : vmList) {
                    if (vmToHost.get(vm) == host) {
                        any = true;
                        allocated.add(vm);
                        System.out.printf("      - VM %2d (MIPS: %4.0f | PEs: %d | RAM: %d MB)%n",
                                vm.getId(), vm.getMips(), vm.getPesNumber(), vm.getRam().getCapacity());
                    }
                }
                if (!any)
                    System.out.println("      (tidak ada VM)");
            }
        }

        List<Vm> failed = new ArrayList<>();
        for (Vm vm : vmList)
            if (!allocated.contains(vm))
                failed.add(vm);
        if (!failed.isEmpty()) {
            System.out.println("\n[VM TIDAK TERALOKASI]");
            failed.forEach(vm -> System.out.printf("      - VM %2d (MIPS: %4.0f | PEs: %d)%n",
                    vm.getId(), vm.getMips(), vm.getPesNumber()));
        }
        System.out.println("===============================================================");
    }

    // ------------------------------------------------------------------
    // Simulasi
    // ------------------------------------------------------------------
    private static void runScenario(String algorithm, int taskCount) {
        CloudSimPlus simulation = new CloudSimPlus();

        List<Datacenter> dcList = createDatacenters(simulation);
        List<Vm> vmList = createVms();

        DatacenterBroker broker = createBroker(simulation, dcList);
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

        simulation.start();

        printMetrics(algorithm, taskCount, broker, vmList, sr.predictedMakespan);
    }

    private static List<Host> createHosts(long seed) {
        List<Host> hostList = new ArrayList<>();
        Random rand = new Random(seed);
        for (int i = 0; i < HOST_COUNT; i++) {
            int peCount = 4 + rand.nextInt(13);
            long mipsPerPe = 1000 + rand.nextInt(2001);
            long ram = 4096 + rand.nextInt(12289);
            List<Pe> peList = new ArrayList<>();
            for (int p = 0; p < peCount; p++)
                peList.add(new PeSimple(mipsPerPe));
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
        String path = "/GoCJ_Dataset/GoCJ_Dataset_" + n + ".txt";
        List<Long> lengths = new ArrayList<>();
        try (InputStream is = Main.class.getResourceAsStream(path)) {
            if (is != null) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
                String line;
                while ((line = reader.readLine()) != null) {
                    line = line.trim();
                    if (!line.isEmpty())
                        lengths.add(Long.parseLong(line));
                }
            } else {
                // Generasi synthetic dataset jika resource tidak ditemukan
                Random rand = new Random(n * 31L);
                for (int i = 0; i < n; i++) {
                    long length = 1000 + rand.nextInt(9000);
                    lengths.add(length);
                }
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

    // ------------------------------------------------------------------
    // Algoritma penjadwalan
    // ------------------------------------------------------------------
    private static int fastestPe(double[][] avail, int vmIdx) {
        int best = 0;
        for (int p = 1; p < avail[vmIdx].length; p++) {
            if (avail[vmIdx][p] < avail[vmIdx][best])
                best = p;
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
        for (int j = 0; j < vms.size(); j++)
            avail[j] = new double[(int) vms.get(j).getPesNumber()];

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
        for (double[] row : avail)
            for (double t : row)
                predicted = Math.max(predicted, t);
        return new ScheduleResult(result, order, predicted);
    }

    private static ScheduleResult fcfsSchedule(List<Cloudlet> cloudlets, List<Vm> vms) {
        Map<Cloudlet, Vm> result = new IdentityHashMap<>();
        List<Cloudlet> order = new ArrayList<>();
        double[][] avail = new double[vms.size()][];
        for (int j = 0; j < vms.size(); j++)
            avail[j] = new double[(int) vms.get(j).getPesNumber()];

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
        for (double[] row : avail)
            for (double t : row)
                predicted = Math.max(predicted, t);
        return new ScheduleResult(result, order, predicted);
    }

    // ------------------------------------------------------------------
    // Metrik
    // ------------------------------------------------------------------
    private static void printMetrics(String algorithm, int taskCount, DatacenterBroker broker, List<Vm> vmList,
            double predictedMakespan) {
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
            if (makespan > 0)
                utilSum += busyJ / (vm.getPesNumber() * makespan);
            totalCost += finishJ * vm.getMips() * vm.getPesNumber() * COST_PER_MIPS_SEC;
        }
        double avgUtilPct = 100.0 * utilSum / vmList.size();

        double mean = Arrays.stream(finishTimes).average().orElse(0);
        double variance = Arrays.stream(finishTimes).map(t -> (t - mean) * (t - mean)).average().orElse(0);
        double degreeOfImbalance = Math.sqrt(variance);

        double gap = predictedMakespan > 0 ? Math.abs(makespan - predictedMakespan) / predictedMakespan : 0;

        System.out.printf(Locale.US,
                "%-10s | %-6d | %-13.2f | %-13.2f | %-8.2f | %-10.4f | %-9.2f | %-10.2f | %-10.2f%n",
                algorithm, taskCount, predictedMakespan, makespan, gap * 100, throughput,
                avgUtilPct, degreeOfImbalance, totalCost);

        csvRows.add(String.format(Locale.US, "%s,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f",
                algorithm, taskCount, predictedMakespan, makespan, gap * 100, throughput, avgUtilPct, degreeOfImbalance,
                totalCost));
    }

    private static void writeCsv(String filename) {
        try {
            Files.write(Paths.get(filename), String.join("\n", csvRows).getBytes(StandardCharsets.UTF_8));
            System.out.println("\nCSV berhasil disimpan ke: " + filename);
        } catch (IOException e) {
            System.out.println("Gagal menulis CSV: " + e.getMessage());
        }
    }
}