package com.schwab.urlshortener.analytics;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "click_events")
public class ClickEvent {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "link_id", nullable = false)
    private UUID linkId;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    @Column(name = "referrer", length = 512)
    private String referrer;

    @Column(name = "user_agent_category", nullable = false, length = 16)
    private String userAgentCategory;

    @Column(name = "trace_id", nullable = false, length = 64)
    private String traceId;

    protected ClickEvent() {}

    public ClickEvent(
            UUID linkId,
            Instant occurredAt,
            String referrer,
            String userAgentCategory,
            String traceId) {
        this.linkId = linkId;
        this.occurredAt = occurredAt;
        this.referrer = referrer;
        this.userAgentCategory = userAgentCategory;
        this.traceId = traceId;
    }

    public UUID getLinkId() {
        return linkId;
    }

    public Instant getOccurredAt() {
        return occurredAt;
    }

    public String getReferrer() {
        return referrer;
    }

    public String getUserAgentCategory() {
        return userAgentCategory;
    }

    public String getTraceId() {
        return traceId;
    }
}
