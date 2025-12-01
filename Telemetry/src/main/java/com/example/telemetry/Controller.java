package com.example.telemetry;

import javafx.fxml.FXML;
import javafx.scene.control.Label;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;

public class Controller {

    @FXML private Label sessionInfo;
    @FXML private Label flagStatus;
    @FXML private TableView<DriverRow> driverTable;
    @FXML private TableColumn<DriverRow, String> posCol;
    @FXML private TableColumn<DriverRow, String> nameCol;
    @FXML private TableColumn<DriverRow, String> gapCol;
    @FXML private TableColumn<DriverRow, String> compoundCol;
    @FXML private TableColumn<DriverRow, String> pitCol;

    @FXML
    public void initialize() {
        // Collega le colonne al modello DriverRow
        posCol.setCellValueFactory(new PropertyValueFactory<>("position"));
        nameCol.setCellValueFactory(new PropertyValueFactory<>("name"));
        gapCol.setCellValueFactory(new PropertyValueFactory<>("gapToLeader"));
        compoundCol.setCellValueFactory(new PropertyValueFactory<>("compound"));
        pitCol.setCellValueFactory(new PropertyValueFactory<>("pitStops"));

        // Avvia l'aggiornamento live
        DataUpdater.startUpdating(sessionInfo, flagStatus, driverTable);
    }
}