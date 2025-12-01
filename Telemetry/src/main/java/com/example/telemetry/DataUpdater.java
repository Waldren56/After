package com.example.telemetry;

import javafx.application.Platform;
import javafx.collections.ObservableList;
import javafx.scene.control.Label;
import javafx.scene.control.TableView;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class DataUpdater {

    public static void startUpdating(Label sessionInfo, Label flagStatus, TableView<DriverRow> driverTable) {
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
        scheduler.scheduleAtFixedRate(() -> {
            try {
                URL url = new URL("http://localhost:5000/f1-data");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);

                if (conn.getResponseCode() == 200) {
                    BufferedReader in = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = in.readLine()) != null) {
                        response.append(line);
                    }
                    in.close();

                    org.json.JSONObject json = new org.json.JSONObject(response.toString());

                    // Estrai dati sessione
                    String sessionInfoText = json.optString("session_info", "Sconosciuta");
                    org.json.JSONObject sessStatus = json.optJSONObject("session_status");
                    String flag = sessStatus != null ? sessStatus.optString("flag", "UNKNOWN") : "???";
                    String flagDisplay = switch (flag) {
                        case "RED" -> "Rosso";
                        case "YELLOW", "DOUBLE_YELLOW" -> "Giallo";
                        case "GREEN" -> "Verde";
                        case "CHEQUERED" -> "A scacchi";
                        default -> flag;
                    };

                    // Estrai piloti
                    ObservableList<DriverRow> drivers = driverTable.getItems();
                    drivers.clear();
                    var driversArray = json.getJSONArray("drivers");
                    for (int i = 0; i < driversArray.length(); i++) {
                        var d = driversArray.getJSONObject(i);
                        String gap = "";
                        if (d.has("gap_to_leader") && !d.isNull("gap_to_leader")) {
                            double g = d.getDouble("gap_to_leader");
                            if (g > 0) gap = "+" + String.format("%.3f", g).replaceAll("0*$", "").replaceAll("\\.$", "");
                        }
                        drivers.add(new DriverRow(
                                String.valueOf(d.getInt("position")),
                                d.getString("driver_name"),
                                d.getString("team"),
                                gap,
                                d.getString("compound"),
                                String.valueOf(d.getInt("pit_stops"))
                        ));
                    }

                    // Aggiorna GUI
                    String finalSessionInfo = sessionInfoText;
                    String finalFlagDisplay = "Bandiera: " + flagDisplay;
                    Platform.runLater(() -> {
                        sessionInfo.setText(finalSessionInfo);
                        flagStatus.setText(finalFlagDisplay);
                        // Opzionale: colora la bandiera
                        String color = "white";
                        if ("RED".equals(flag)) color = "red";
                        else if ("YELLOW".equals(flag) || "DOUBLE_YELLOW".equals(flag)) color = "yellow";
                        else if ("GREEN".equals(flag)) color = "green";
                        flagStatus.setStyle("-fx-text-fill: " + color + ";");
                    });

                }
            } catch (Exception e) {
                Platform.runLater(() -> sessionInfo.setText("❌ Errore: " + e.getMessage()));
            }
        }, 0, 2, TimeUnit.SECONDS);
    }
}