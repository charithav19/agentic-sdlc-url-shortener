package com.schwab.urlshortener;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import org.junit.jupiter.api.Test;

class BootstrapTest {
    @Test
    void applicationTypeExists() {
        assertNotNull(UrlShortenerApplication.class);
    }
}
