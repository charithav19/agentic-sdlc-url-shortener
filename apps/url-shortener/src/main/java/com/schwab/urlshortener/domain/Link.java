package com.schwab.urlshortener.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "links",
        uniqueConstraints =
                @UniqueConstraint(name = "uk_links_short_code", columnNames = "short_code"))
public class Link {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "short_code", nullable = false, length = 32, unique = true)
    private String shortCode;

    @Column(name = "original_url", nullable = false, columnDefinition = "text")
    private String url;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 16)
    private LinkStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Version
    @Column(name = "version", nullable = false)
    private long version;

    protected Link() {}

    public Link(String shortCode, String url, Instant createdAt) {
        this(shortCode, url, createdAt, null);
    }

    public Link(String shortCode, String url, Instant createdAt, Instant expiresAt) {
        this.shortCode = shortCode;
        this.url = url;
        this.createdAt = createdAt;
        this.expiresAt = expiresAt;
        this.status = LinkStatus.ACTIVE;
    }

    public void disable() {
        status = LinkStatus.DISABLED;
    }

    public UUID getId() {
        return id;
    }

    public String getShortCode() {
        return shortCode;
    }

    public String getUrl() {
        return url;
    }

    public LinkStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }
}
