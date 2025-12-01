package com.example.telemetry;// Per WebView e WebEngine

import javafx.scene.web.WebView;
import javafx.scene.web.WebEngine;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.IOException;

// Per FXML
import javafx.fxml.FXML;

// Per thread e aggiornamento
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

// Per aggiornare la GUI dal thread
import javafx.application.Platform;

public class WebController {
    @FXML
    private WebView webView;

    @FXML
    public void initialize() {
        WebEngine engine = webView.getEngine();
        // Carica una pagina HTML locale
        engine.load(getClass().getResource("f1-dashboard.html").toExternalForm());

        // Oppure carica HTML inline
        // engine.loadContent("<html>...</html>");

        // Avvia aggiornamento live
        startLiveUpdate(engine);
    }

    private void startLiveUpdate(WebEngine engine) {
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
        scheduler.scheduleAtFixedRate(() -> {
            try {
                // Recupera JSON da Python (come prima)
                String jsonData = fetchJsonFromPython();

                // Invia i dati a JavaScript
                Platform.runLater(() -> {
                    engine.executeScript("updateDashboard(" + jsonData + ")");
                });
            } catch (Exception e) {
                e.printStackTrace();
            }
        }, 0, 2, TimeUnit.SECONDS);
    }

    private String fetchJsonFromPython() throws IOException {
        URL url = new URL("http://localhost:5000/f1-data");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(3000);
        conn.setReadTimeout(3000);

        if (conn.getResponseCode() == 200) {
            try (BufferedReader in = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                return in.lines().collect(StringBuilder::new, StringBuilder::append, StringBuilder::append).toString();
            }
        } else {
            throw new IOException("HTTP " + conn.getResponseCode());
        }
    }
}