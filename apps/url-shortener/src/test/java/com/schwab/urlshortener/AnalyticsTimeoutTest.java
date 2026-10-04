package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.schwab.urlshortener.application.LinkService;
import io.micrometer.core.instrument.MeterRegistry;
import java.sql.Connection;
import java.sql.Statement;
import java.util.concurrent.TimeUnit;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class AnalyticsTimeoutTest extends UrlIntegrationTestSupport {
    @Autowired MockMvc client;
    @Autowired LinkService linksService;
    @Autowired MeterRegistry registry;
    @Autowired DataSource dataSource;

    @Test
    void databaseWriteTimeoutDoesNotPreventValidRedirect() throws Exception {
        String code =
                linksService
                        .create("https://example.com/valid", "locked_events", null)
                        .getShortCode();
        double before = registry.get("url.analytics.failure").counter().count();
        try (Connection blocker = dataSource.getConnection()) {
            blocker.setAutoCommit(false);
            try {
                try (Statement statement = blocker.createStatement()) {
                    statement.execute("LOCK TABLE click_events IN ACCESS EXCLUSIVE MODE");
                }
                client.perform(get("/{code}", code))
                        .andExpect(status().isFound())
                        .andExpect(header().string("Location", "https://example.com/valid"));
                long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(6);
                while (failureCount() < before + 1 && System.nanoTime() < deadline) {
                    Thread.sleep(20);
                }
                assertThat(failureCount()).isGreaterThanOrEqualTo(before + 1);
            } finally {
                blocker.rollback();
            }
        }
        assertThat(events.count()).isZero();
    }

    private double failureCount() {
        return registry.get("url.analytics.failure").counter().count();
    }
}
