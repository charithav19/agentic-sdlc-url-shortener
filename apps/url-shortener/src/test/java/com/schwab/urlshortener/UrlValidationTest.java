package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.schwab.urlshortener.domain.InvalidUrlException;
import com.schwab.urlshortener.domain.UrlValidator;
import org.junit.jupiter.api.Test;

class UrlValidationTest {
    private final UrlValidator validator = new UrlValidator();

    @Test
    void acceptsAbsoluteHttpAndHttpsUrls() {
        assertThat(validator.validate("http://example.com/a?b=c"))
                .isEqualTo("http://example.com/a?b=c");
        assertThat(validator.validate("https://example.com/path"))
                .isEqualTo("https://example.com/path");
    }

    @Test
    void rejectsUnsupportedOrMalformedUrls() {
        for (String value :
                new String[] {
                    "ftp://example.com",
                    "file:///etc/passwd",
                    "/path",
                    "http://",
                    "http://example.com/a b"
                }) {
            assertThatThrownBy(() -> validator.validate(value))
                    .isInstanceOf(InvalidUrlException.class);
        }
    }

    @Test
    void rejectsCredentialsAndControls() {
        for (String value :
                new String[] {
                    "https://user:password@example.com", "https://example.com/\r\nInjected"
                }) {
            assertThatThrownBy(() -> validator.validate(value))
                    .isInstanceOf(InvalidUrlException.class);
        }
    }
}
