# =============================================================================
# AION Flink Sales Aggregator — Multi-stage Build
# =============================================================================

# --- Stage 1: Build ---
FROM maven:3.9-eclipse-temurin-17-alpine AS builder

WORKDIR /build

# Cache dependencies first
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source and build fat jar
COPY src/ src/
RUN mvn clean package -DskipTests -B

# --- Stage 2: Runtime ---
FROM flink:1.18.1-java17

# Labels
LABEL maintainer="aion-platform"
LABEL description="AION Flink Sales Aggregation Job"

# Flink user owns the job artifacts
USER root

# Create directories for checkpoints and savepoints
RUN mkdir -p /opt/flink/usrlib /tmp/flink-checkpoints /tmp/flink-savepoints && \
    chown -R flink:flink /tmp/flink-checkpoints /tmp/flink-savepoints

# Copy the built jar
COPY --from=builder /build/target/aion-flink-sales-aggregator-1.0.0.jar /opt/flink/usrlib/aion-sales-aggregator.jar

# Copy Flink configuration overrides
COPY src/main/resources/flink-conf.yaml /opt/flink/conf/flink-conf.yaml

USER flink

# Default entrypoint is inherited from flink base image (jobmanager/taskmanager)
# Override CMD at runtime: jobmanager | taskmanager | standalone
ENTRYPOINT ["/docker-entrypoint.sh"]
