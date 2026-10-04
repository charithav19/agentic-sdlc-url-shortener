package com.schwab.urlshortener;

import com.schwab.urlshortener.analytics.ClickEventRepository;
import com.schwab.urlshortener.persistence.IdempotencyRepository;
import com.schwab.urlshortener.persistence.LinkRepository;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

abstract class UrlIntegrationTestSupport {
    private static final String IMAGE =
            "postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2";

    static final PostgreSQLContainer postgres =
            new PostgreSQLContainer(
                    DockerImageName.parse(IMAGE).asCompatibleSubstituteFor("postgres"));

    static {
        postgres.start();
    }

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired LinkRepository links;
    @Autowired IdempotencyRepository records;
    @Autowired ClickEventRepository events;

    @BeforeEach
    void clearDatabase() {
        events.deleteAll();
        records.deleteAll();
        links.deleteAll();
    }
}
