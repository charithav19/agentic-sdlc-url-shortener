package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import java.time.Clock;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(properties = "shortener.analytics.enabled=false")
@AutoConfigureMockMvc
@Import(ExpiryTest.FixedClockConfiguration.class)
class ExpiryTest extends UrlIntegrationTestSupport {
    private static final Instant START = Instant.parse("2026-10-04T12:00:00Z");
    @Autowired MockMvc client;
    @Autowired LinkService service;
    @Autowired Clock clock;

    @Test
    void redirectsUntilExactExpiryThenReturns410() throws Exception {
        MutableClock mutable = (MutableClock) clock;
        mutable.set(START);
        String code =
                service.create("https://example.com/a", "expires_soon", START.plusSeconds(5))
                        .getShortCode();
        mutable.set(START.plusSeconds(4));
        client.perform(get("/{code}", code)).andExpect(status().isFound());
        mutable.set(START.plusSeconds(5));
        client.perform(get("/{code}", code))
                .andExpect(status().isGone())
                .andExpect(jsonPath("$.code").value("LINK_GONE"));
        assertThat(links.count()).isEqualTo(1);
    }

    @Test
    void rejectsExpiryAtOrBeforeCreationTime() throws Exception {
        ((MutableClock) clock).set(START);
        for (String expiry : new String[] {"2026-10-04T12:00:00Z", "2026-10-04T11:59:59Z"}) {
            client.perform(
                            post("/api/v1/links")
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(
                                            "{\"url\":\"https://example.com\",\"expiresAt\":\""
                                                    + expiry
                                                    + "\"}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.code").value("INVALID_EXPIRY"));
        }
        assertThat(links.count()).isZero();
    }

    @TestConfiguration
    static class FixedClockConfiguration {
        @Bean
        @Primary
        Clock fixedTestClock() {
            return new MutableClock(START);
        }
    }
}
