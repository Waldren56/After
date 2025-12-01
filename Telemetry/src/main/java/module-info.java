module com.example.telemetry {
    requires javafx.controls;
    requires javafx.fxml;
    requires static org.json;
    requires javafx.web;

    requires org.controlsfx.controls;
    requires net.synedra.validatorfx;
    requires org.kordamp.bootstrapfx.core;

    opens com.example.telemetry to javafx.fxml;
    exports com.example.telemetry;
}