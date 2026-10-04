package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.domain.Link;
import java.time.Clock;
import java.time.Instant;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
@Import(AnalyticsTest.ControlledClockConfiguration.class)
class AnalyticsTest extends UrlIntegrationTestSupport {
    private static final Instant START = Instant.parse("2026-10-04T23:59:59Z");
    @Autowired MockMvc client;
    @Autowired LinkService linksService;
    @Autowired Clock clock;

    @Test
    void successfulRedirectsPersistSanitizedEventsAndAggregateByUtcDay() throws Exception {
        MutableClock mutable = (MutableClock) clock;
        mutable.set(START);
        Link link = linksService.create("https://example.com/destination", "analytics_link", null);

        MvcResult first =
                client.perform(
                                get("/{code}", link.getShortCode())
                                        .header(
                                                "Referer",
                                                "https://Ref.Example/secret?token=private")
                                        .header("User-Agent", "Mobile Safari"))
                        .andExpect(status().isFound())
                        .andExpect(header().string("Location", "https://example.com/destination"))
                        .andReturn();
        awaitEvents(1);
        assertThat(events.findAll().getFirst().getLinkId()).isEqualTo(link.getId());
        assertThat(events.findAll().getFirst().getOccurredAt()).isEqualTo(START);
        assertThat(events.findAll().getFirst().getReferrer()).isEqualTo("https://ref.example");
        assertThat(events.findAll().getFirst().getUserAgentCategory()).isEqualTo("MOBILE");
        assertThat(events.findAll().getFirst().getTraceId())
                .isEqualTo(first.getResponse().getHeader("X-Trace-Id"));

        mutable.set(START.plusSeconds(2));
        client.perform(get("/{code}", link.getShortCode()).header("User-Agent", "ExampleBot"))
                .andExpect(status().isFound());
        awaitEvents(2);
        assertThat(events.findAll())
                .anySatisfy(
                        event -> {
                            assertThat(event.getUserAgentCategory()).isEqualTo("BOT");
                            assertThat(event.getReferrer()).isNull();
                        });
        client.perform(get("/api/v1/links/{code}/analytics", link.getShortCode()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.shortCode").value(link.getShortCode()))
                .andExpect(jsonPath("$.totalClicks").value(2))
                .andExpect(jsonPath("$.clicksByDay['2026-10-04']").value(1))
                .andExpect(jsonPath("$.clicksByDay['2026-10-05']").value(1));
    }

    @Test
    void metadataAndUnsuccessfulRedirectsDoNotCreateEvents() throws Exception {
        ((MutableClock) clock).set(START);
        Link link = linksService.create("https://example.com/a", "no_clicks", START.plusSeconds(1));
        client.perform(get("/api/v1/links/{code}", link.getShortCode())).andExpect(status().isOk());
        client.perform(get("/missing")).andExpect(status().isNotFound());
        ((MutableClock) clock).set(START.plusSeconds(1));
        client.perform(get("/{code}", link.getShortCode())).andExpect(status().isGone());
        client.perform(get("/api/v1/links/missing/analytics")).andExpect(status().isNotFound());
        client.perform(get("/api/v1/links/{code}/analytics", link.getShortCode()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalClicks").value(0));
        assertThat(events.count()).isZero();
    }

    private void awaitEvents(long expected) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (events.count() < expected && System.nanoTime() < deadline) {
            Thread.sleep(20);
        }
        assertThat(events.count()).isEqualTo(expected);
    }

    @TestConfiguration
    static class ControlledClockConfiguration {
        @Bean
        @Primary
        Clock analyticsTestClock() {
            return new MutableClock(START);
        }
    }
}
