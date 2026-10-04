package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.schwab.urlshortener.application.CollisionExhaustedException;
import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.domain.ShortCodeGenerator;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;

@SpringBootTest(properties = "shortener.analytics.enabled=false")
@Import(CollisionTest.GeneratorConfiguration.class)
class CollisionTest extends UrlIntegrationTestSupport {
    @Autowired LinkService service;
    @Autowired QueueGenerator generator;

    @Test
    void retriesCollisionAndKeepsTransactionUsable() {
        service.create("https://example.com/seed", "Dup0123", null);
        generator.offer("Dup0123", "Fresh45");
        assertThat(service.create("https://example.com/new").getShortCode()).isEqualTo("Fresh45");
        assertThat(generator.calls()).isEqualTo(2);
        assertThat(links.count()).isEqualTo(2);
    }

    @Test
    void stopsAfterFiveTotalAttemptsAndNextRequestStillWorks() {
        service.create("https://example.com/seed", "Dup0123", null);
        generator.offer("Dup0123", "Dup0123", "Dup0123", "Dup0123", "Dup0123", "Recover");
        assertThatThrownBy(() -> service.create("https://example.com/blocked"))
                .isInstanceOf(CollisionExhaustedException.class);
        assertThat(generator.calls()).isEqualTo(5);
        assertThat(links.count()).isEqualTo(1);
        assertThat(service.create("https://example.com/after").getShortCode()).isEqualTo("Recover");
    }

    static class QueueGenerator implements ShortCodeGenerator {
        private final ConcurrentLinkedQueue<String> codes = new ConcurrentLinkedQueue<>();
        private final AtomicInteger calls = new AtomicInteger();

        void offer(String... values) {
            calls.set(0);
            codes.clear();
            for (String value : values) {
                codes.add(value);
            }
        }

        int calls() {
            return calls.get();
        }

        @Override
        public String generate() {
            calls.incrementAndGet();
            String code = codes.poll();
            if (code == null) {
                throw new AssertionError("Generated more short codes than expected");
            }
            return code;
        }
    }

    @TestConfiguration
    static class GeneratorConfiguration {
        @Bean
        @Primary
        QueueGenerator queueGenerator() {
            return new QueueGenerator();
        }
    }
}
