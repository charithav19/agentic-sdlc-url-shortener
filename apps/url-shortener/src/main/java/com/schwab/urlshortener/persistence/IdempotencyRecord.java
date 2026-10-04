package com.schwab.urlshortener.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "idempotency_records",
        uniqueConstraints =
                @UniqueConstraint(
                        name = "uk_idempotency_scope_key",
                        columnNames = {"caller_scope", "request_key"}))
public class IdempotencyRecord {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "caller_scope", nullable = false, length = 128)
    private String callerScope;

    @Column(name = "request_key", nullable = false, length = 128)
    private String requestKey;

    @Column(name = "request_fingerprint", nullable = false, length = 64)
    private String requestFingerprint;

    @Column(name = "link_id", nullable = false)
    private UUID linkId;

    @Column(name = "response_json", nullable = false, columnDefinition = "text")
    private String responseJson;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected IdempotencyRecord() {}

    public IdempotencyRecord(
            String callerScope,
            String requestKey,
            String requestFingerprint,
            UUID linkId,
            String responseJson,
            Instant createdAt) {
        this.callerScope = callerScope;
        this.requestKey = requestKey;
        this.requestFingerprint = requestFingerprint;
        this.linkId = linkId;
        this.responseJson = responseJson;
        this.createdAt = createdAt;
    }

    public String getRequestFingerprint() {
        return requestFingerprint;
    }

    public String getResponseJson() {
        return responseJson;
    }
}
