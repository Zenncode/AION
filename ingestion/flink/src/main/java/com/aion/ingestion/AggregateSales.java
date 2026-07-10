package com.aion.ingestion;

import java.io.Serializable;
import java.math.BigDecimal;

public class AggregateSales implements Serializable {

    private static final long serialVersionUID = 1L;

    private String windowStart;
    private String windowEnd;
    private String region;
    private String currency;
    private long orderCount;
    private long totalQuantity;
    private BigDecimal totalRevenue;
    private BigDecimal averageOrderValue;
    private long uniqueCustomers;

    public AggregateSales() {}

    public AggregateSales(String windowStart, String windowEnd, String region, String currency,
                          long orderCount, long totalQuantity, BigDecimal totalRevenue,
                          BigDecimal averageOrderValue, long uniqueCustomers) {
        this.windowStart = windowStart;
        this.windowEnd = windowEnd;
        this.region = region;
        this.currency = currency;
        this.orderCount = orderCount;
        this.totalQuantity = totalQuantity;
        this.totalRevenue = totalRevenue;
        this.averageOrderValue = averageOrderValue;
        this.uniqueCustomers = uniqueCustomers;
    }

    // Getters and setters
    public String getWindowStart() { return windowStart; }
    public void setWindowStart(String windowStart) { this.windowStart = windowStart; }

    public String getWindowEnd() { return windowEnd; }
    public void setWindowEnd(String windowEnd) { this.windowEnd = windowEnd; }

    public String getRegion() { return region; }
    public void setRegion(String region) { this.region = region; }

    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }

    public long getOrderCount() { return orderCount; }
    public void setOrderCount(long orderCount) { this.orderCount = orderCount; }

    public long getTotalQuantity() { return totalQuantity; }
    public void setTotalQuantity(long totalQuantity) { this.totalQuantity = totalQuantity; }

    public BigDecimal getTotalRevenue() { return totalRevenue; }
    public void setTotalRevenue(BigDecimal totalRevenue) { this.totalRevenue = totalRevenue; }

    public BigDecimal getAverageOrderValue() { return averageOrderValue; }
    public void setAverageOrderValue(BigDecimal averageOrderValue) { this.averageOrderValue = averageOrderValue; }

    public long getUniqueCustomers() { return uniqueCustomers; }
    public void setUniqueCustomers(long uniqueCustomers) { this.uniqueCustomers = uniqueCustomers; }

    @Override
    public String toString() {
        return "AggregateSales{" +
                "windowStart='" + windowStart + '\'' +
                ", windowEnd='" + windowEnd + '\'' +
                ", region='" + region + '\'' +
                ", currency='" + currency + '\'' +
                ", orderCount=" + orderCount +
                ", totalQuantity=" + totalQuantity +
                ", totalRevenue=" + totalRevenue +
                ", averageOrderValue=" + averageOrderValue +
                ", uniqueCustomers=" + uniqueCustomers +
                '}';
    }
}
