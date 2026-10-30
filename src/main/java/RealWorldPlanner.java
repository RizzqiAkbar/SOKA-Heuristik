package org.example;

import org.cloudsimplus.cloudlets.Cloudlet;
import org.cloudsimplus.vms.Vm;
import org.cloudsimplus.vms.VmSimple;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Max-Min yang sama dengan Main, tapi VM-nya adalah node cluster sungguhan
 * (nodes.csv), bukan VM acak. Hasilnya plan.csv: task mana dijalankan di node mana.
 *
 * Pakai: RealWorldPlanner <nTask> <nodes.csv> <targetDetik> <plan.csv>
 */
public class RealWorldPlanner {

    // 1 MI = 100.000 iterasi loop. MIPS node = iterasi per detik / 100.000.
    private static final double ITERS_PER_MI = 100_000;

    public static void main(String[] args) throws IOException {
        int taskCount = Integer.parseInt(args[0]);
        double targetSeconds = Double.parseDouble(args[2]);

        // 1. Baca node (baris: nama,jumlah_vCPU,iterasi_per_detik) -> jadikan Vm
        List<String> nodeNames = new ArrayList<>();
        List<Vm> vms = new ArrayList<>();
        List<String> lines = Files.readAllLines(Paths.get(args[1]));
        for (String line : lines.subList(1, lines.size())) {
            if (line.isBlank()) continue;
            String[] f = line.split(",");
            nodeNames.add(f[0].trim());
            vms.add(new VmSimple(Double.parseDouble(f[2]) / ITERS_PER_MI, Integer.parseInt(f[1].trim())));
        }

        // 2. Jalankan Max-Min yang sama persis dengan simulasi
        List<Cloudlet> cloudlets = Main.loadGoCJDataset(taskCount);
        Main.ScheduleResult sr = Main.maxMinSchedule(cloudlets, vms);

        // 3. Panjang task diperkecil seragam supaya demo singkat (keputusan Max-Min tidak berubah)
        double scale = targetSeconds / sr.predictedMakespan;

        Map<Vm, String> nodeOf = new IdentityHashMap<>(); // identitas objek, bukan equals()
        for (int i = 0; i < vms.size(); i++) nodeOf.put(vms.get(i), nodeNames.get(i));
        Map<Cloudlet, Integer> taskId = new IdentityHashMap<>();
        for (int i = 0; i < cloudlets.size(); i++) taskId.put(cloudlets.get(i), i);

        // 4. Tulis plan: urutan = urutan keputusan Max-Min
        StringBuilder plan = new StringBuilder("# prediksi=" + targetSeconds + "\nseq,task_id,node,iterations\n");
        int seq = 0;
        for (Cloudlet c : sr.order) {
            long iterations = Math.round(c.getLength() * scale * ITERS_PER_MI);
            plan.append(seq++).append(',').append(taskId.get(c)).append(',')
                .append(nodeOf.get(sr.assignment.get(c))).append(',').append(iterations).append('\n');
        }
        Files.writeString(Paths.get(args[3]), plan.toString());
        System.out.println("Plan Max-Min: " + taskCount + " task -> " + args[3] + ", prediksi makespan " + targetSeconds + " detik");
    }
}
