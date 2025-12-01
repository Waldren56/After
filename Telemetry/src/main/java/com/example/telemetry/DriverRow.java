package com.example.telemetry;

import javafx.beans.property.SimpleStringProperty;

public class DriverRow {
    public final SimpleStringProperty position;
    public final SimpleStringProperty name;
    public final SimpleStringProperty team;
    public final SimpleStringProperty gapToLeader;
    public final SimpleStringProperty compound;
    public final SimpleStringProperty pitStops;

    public DriverRow(String position, String name, String team, String gapToLeader, String compound, String pitStops) {
        this.position = new SimpleStringProperty(position);
        this.name = new SimpleStringProperty(name);
        this.team = new SimpleStringProperty(team);
        this.gapToLeader = new SimpleStringProperty(gapToLeader);
        this.compound = new SimpleStringProperty(compound);
        this.pitStops = new SimpleStringProperty(pitStops);
    }

    // GETTER OBBLIGATORI per PropertyValueFactory
    public String getPosition() { return position.get(); }
    public String getName() { return name.get(); }
    public String getTeam() { return team.get(); }
    public String getGapToLeader() { return gapToLeader.get(); }
    public String getCompound() { return compound.get(); }
    public String getPitStops() { return pitStops.get(); }

    // OPZIONALE: getter per le property (utile per binding avanzato)
    public SimpleStringProperty positionProperty() { return position; }
    public SimpleStringProperty nameProperty() { return name; }
    public SimpleStringProperty gapToLeaderProperty() { return gapToLeader; }
    public SimpleStringProperty compoundProperty() { return compound; }
    public SimpleStringProperty pitStopsProperty() { return pitStops; }
}