package com.schwab.urlshortener.config;

import java.net.URI;
import java.util.Locale;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "shortener")
public record ShortUrlProperties(String baseUrl) {
    public ShortUrlProperties {
        URI uri;
        try {
            uri = URI.create(baseUrl);
        } catch (IllegalArgumentException | NullPointerException exception) {
            throw new IllegalArgumentException(
                    "shortener.base-url must be an absolute HTTP or HTTPS URL", exception);
        }
        String scheme = uri.getScheme();
        if (scheme == null
                || !(scheme.toLowerCase(Locale.ROOT).equals("http")
                        || scheme.toLowerCase(Locale.ROOT).equals("https"))
                || uri.getHost() == null
                || uri.getRawUserInfo() != null
                || uri.getRawQuery() != null
                || uri.getRawFragment() != null) {
            throw new IllegalArgumentException(
                    "shortener.base-url must be an absolute HTTP or HTTPS URL without credentials, query or fragment");
        }
        baseUrl = baseUrl.replaceAll("/+$", "");
    }

    public String shortUrl(String code) {
        return baseUrl + "/" + code;
    }
}
