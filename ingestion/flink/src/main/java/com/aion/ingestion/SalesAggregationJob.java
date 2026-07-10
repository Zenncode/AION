package com.aion.ingestion;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashSet;
import java.util.Set;
import java.util.Properties;

/**
 * Flink job: consume legacy.orders → 5-min tumbling window aggregation → produce to aggregated.sales.
 *
 * Stateful windowing calculates per-region, per-currency aggregates:
 *   - order count, total quantity, total revenue, average order value, unique customers
 *
 * Late events (beyond 1-minute tolerance) are routed to a side output for monitoring.
 */
public class SalesAggregationJob {

    private static final String INPUT_TOPIC = "legacy.orders";
    private static final String OUTPUT_TOPIC = "aggregated.sales";
    private static final String DEAD_LETTER_TOPIC = "aggregated.sales.dlq";
    private static final long WINDOW_SIZE_MINUTES = 5;
    private static final long LATE_TOLERANCE_MINUTES = 1;
    private static final DateTimeFormatter ISO_FORMAT = DateTimeFormatter.ISO_INSTANT.withZone(ZoneOffset.UTC);

    public static void main(String[] args) throws Exception {
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // Checkpointing every 60s with exactly-once
        env.enableCheckpointing(60_000);
        env.getCheckpointConfig().setCheckpointingMode(
                org.apache.flink.streaming.api.CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000);
        env.getCheckpointConfig().setCheckpointTimeout(120_000);
        env.getCheckpointConfig().setTolerableCheckpointFailureNumber(3);
        env.getCheckpointConfig().setExternalizedCheckpointCleanup(
                org.apache.flink.streaming.api.CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);

        // Parallelism from env or default 4
        env.setParallelism(Integer.parseInt(
                System.getenv().getOrDefault("FLINK_PARALLELISM", "4")));

        // --- Source: Kafka legacy.orders ---
        String bootstrapServers = System.getenv().getOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092");

        KafkaSource<String> kafkaSource = KafkaSource.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setTopics(INPUT_TOPIC)
                .setGroupId("aion-flink-sales-aggregator")
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        // Watermark strategy: bounded out-of-orderness of 1 minute
        WatermarkStrategy<String> watermarkStrategy = WatermarkStrategy
                .<String>forBoundedOutOfOrderness(Duration.ofMinutes(LATE_TOLERANCE_MINUTES))
                .withTimestampAssigner((event, timestamp) -> extractEventTime(event));

        DataStream<String> rawStream = env.fromSource(
                kafkaSource, watermarkStrategy, "Kafka Source - legacy.orders");

        // --- Parse JSON → OrderEvent ---
        final ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

        OutputTag<String> lateEventsTag = new OutputTag<String>("late-events") {};

        SingleOutputStreamOperator<OrderEvent> parsedStream = rawStream
                .process(new org.apache.flink.streaming.api.functions.ProcessFunction<String, OrderEvent>() {
                    @Override
                    public void processElement(String value, Context ctx, Collector<OrderEvent> out) {
                        try {
                            OrderEvent event = mapper.readValue(value, OrderEvent.class);
                            out.collect(event);
                        } catch (Exception e) {
                            // Route parse failures to dead letter queue
                            ctx.output(lateEventsTag, value);
                        }
                    }
                });

        // --- Windowed Aggregation: 5-minute tumbling windows ---
        SingleOutputStreamOperator<String> aggregatedStream = parsedStream
                .keyBy(event -> event.getRegion() + "|" + event.getCurrency())
                .window(TumblingEventTimeWindows.of(Time.minutes(WINDOW_SIZE_MINUTES)))
                .allowedLateness(Time.minutes(LATE_TOLERANCE_MINUTES))
                .sideOutputLateData(lateEventsTag)
                .aggregate(new SalesAggregateFunction(), new SalesWindowFunction());

        // --- Sink: Kafka aggregated.sales ---
        KafkaSink<String> kafkaSink = KafkaSink.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(OUTPUT_TOPIC)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        aggregatedStream.sinkTo(kafkaSink).name("Kafka Sink - aggregated.sales");

        // --- Dead Letter Queue for late/failed events ---
        KafkaSink<String> dlqSink = KafkaSink.<String>builder()
                .setBootstrapServers(bootstrapServers)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(DEAD_LETTER_TOPIC)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .build();

        parsedStream.getSideOutput(lateEventsTag).sinkTo(dlqSink).name("Kafka Sink - DLQ");

        env.execute("AION Sales Aggregation Job");
    }

    /**
     * Extract event time (created_at) from raw JSON string.
     * Falls back to current time if parsing fails.
     */
    private static long extractEventTime(String json) {
        try {
            // Quick regex extraction to avoid full parse before watermark assignment
            int idx = json.indexOf("\"created_at\"");
            if (idx < 0) return System.currentTimeMillis();
            String sub = json.substring(idx);
            int start = sub.indexOf("\"", 14) + 1;
            int end = sub.indexOf("\"", start);
            String ts = sub.substring(start, end);
            return Instant.parse(ts).toEpochMilli();
        } catch (Exception e) {
            return System.currentTimeMillis();
        }
    }

    // -------------------------------------------------------------------------
    // AggregateFunction: incremental aggregation within each window
    // -------------------------------------------------------------------------

    public static class SalesAggregateFunction
            implements AggregateFunction<OrderEvent, SalesAccumulator, SalesAccumulator> {

        @Override
        public SalesAccumulator createAccumulator() {
            return new SalesAccumulator();
        }

        @Override
        public SalesAccumulator add(OrderEvent event, SalesAccumulator acc) {
            acc.orderCount++;
            acc.totalQuantity += event.getQuantity();
            acc.totalRevenue = acc.totalRevenue.add(event.getTotalAmount());
            acc.uniqueCustomerIds.add(event.getCustomerId());
            acc.region = event.getRegion();
            acc.currency = event.getCurrency();
            return acc;
        }

        @Override
        public SalesAccumulator getResult(SalesAccumulator acc) {
            return acc;
        }

        @Override
        public SalesAccumulator merge(SalesAccumulator a, SalesAccumulator b) {
            a.orderCount += b.orderCount;
            a.totalQuantity += b.totalQuantity;
            a.totalRevenue = a.totalRevenue.add(b.totalRevenue);
            a.uniqueCustomerIds.addAll(b.uniqueCustomerIds);
            return a;
        }
    }

    /**
     * Mutable accumulator for incremental aggregation.
     */
    public static class SalesAccumulator implements java.io.Serializable {
        long orderCount = 0;
        long totalQuantity = 0;
        BigDecimal totalRevenue = BigDecimal.ZERO;
        Set<Long> uniqueCustomerIds = new HashSet<>();
        String region;
        String currency;
    }

    // -------------------------------------------------------------------------
    // WindowFunction: adds window metadata and emits final AggregateSales
    // -------------------------------------------------------------------------

    public static class SalesWindowFunction
            implements org.apache.flink.streaming.api.functions.windowing.WindowFunction<
            SalesAccumulator, String, String, TimeWindow> {

        private static final ObjectMapper mapper = new ObjectMapper();

        @Override
        public void apply(String key, TimeWindow window, Iterable<SalesAccumulator> input,
                          Collector<String> out) throws Exception {
            SalesAccumulator acc = input.iterator().next();

            BigDecimal avgOrderValue = acc.orderCount > 0
                    ? acc.totalRevenue.divide(BigDecimal.valueOf(acc.orderCount), 2, RoundingMode.HALF_UP)
                    : BigDecimal.ZERO;

            AggregateSales result = new AggregateSales(
                    ISO_FORMAT.format(Instant.ofEpochMilli(window.getStart())),
                    ISO_FORMAT.format(Instant.ofEpochMilli(window.getEnd())),
                    acc.region,
                    acc.currency,
                    acc.orderCount,
                    acc.totalQuantity,
                    acc.totalRevenue,
                    avgOrderValue,
                    acc.uniqueCustomerIds.size()
            );

            out.collect(mapper.writeValueAsString(result));
        }
    }
}
