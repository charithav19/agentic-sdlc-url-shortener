package com.schwab.urlshortener.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "links")
public class Link {
    @Id @GeneratedValue private Long id;
    @Column(name = "original_url", nullable = false, length = 2048)
    private String originalUrl;
    @Column(name = "short_code", nullable = false, unique = true, length = 7)
    private String shortCode;

    protected Link() {}

    public Link(String originalUrl, String shortCode) {
        this.originalUrl = originalUrl;
        this.shortCode = shortCode;
    }

    public Long getId() { return id; }
    public String getOriginalUrl() { return originalUrl; }
    public String getShortCode() { return shortCode; }
}
