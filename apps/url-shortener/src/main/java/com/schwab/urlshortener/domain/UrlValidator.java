package com.schwab.urlshortener.domain;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public class UrlValidator {
    public String validate(String value) {
        if (value == null || value.isBlank()) {
            throw new InvalidUrlException("URL is required");
        }
        for (int i = 0; i < value.length(); i++) {
            char character = value.charAt(i);
            if (character < 0x20 || character == 0x7F) {
                throw new InvalidUrlException("URL contains a control character");
            }
        }
        try {
            URI uri = new URI(value);
            String scheme = uri.getScheme();
            if (scheme == null
                    || !(scheme.toLowerCase(Locale.ROOT).equals("http")
                            || scheme.toLowerCase(Locale.ROOT).equals("https"))
                    || uri.getHost() == null
                    || uri.getHost().isBlank()) {
                throw new InvalidUrlException(
                        "URL must be an absolute HTTP or HTTPS URL with a host");
            }
            if (uri.getRawUserInfo() != null) {
                throw new InvalidUrlException("URL must not contain embedded credentials");
            }
            return value;
        } catch (URISyntaxException exception) {
            throw new InvalidUrlException("URL is malformed");
        }
    }
}
