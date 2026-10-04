package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureObservability
class ObservabilityTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired LinkService linksService;
    @Autowired MeterRegistry registry;

    @Autowired
    @Qualifier("analyticsExecutor")
    ThreadPoolTaskExecutor executor;

    @Test
    void exposesHealthReadinessMetricsPrometheusAndOpenApiWithoutSensitiveActuatorRoutes()
            throws Exception {
        client.perform(get("/actuator/health")).andExpect(status().isOk());
        client.perform(get("/actuator/health/readiness")).andExpect(status().isOk());
        client.perform(get("/actuator/prometheus")).andExpect(status().isOk());
        client.perform(get("/actuator/metrics/url.redirect.success")).andExpect(status().isOk());
        client.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.paths['/api/v1/links/{shortCode}/analytics'].get").exists());
        client.perform(get("/actuator/env")).andExpect(status().isNotFound());
        assertThat(executor.getThreadPoolExecutor().getMaximumPoolSize()).isEqualTo(2);
        assertThat(executor.getThreadPoolExecutor().getQueue().remainingCapacity())
                .isLessThanOrEqualTo(100);
    }

    @Test
    void successfulRedirectIncrementsLowCardinalityCounter() throws Exception {
        String code =
                linksService.create("https://example.com/a", "metric_link", null).getShortCode();
        double before = registry.get("url.redirect.success").counter().count();
        client.perform(get("/{code}", code)).andExpect(status().isFound());
        assertThat(registry.get("url.redirect.success").counter().count()).isEqualTo(before + 1);
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (events.count() < 1 && System.nanoTime() < deadline) {
            Thread.sleep(20);
        }
        assertThat(events.count()).isEqualTo(1);
    }
}
