package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;

import com.schwab.urlshortener.application.LinkService;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
class LinkRestartTest {
    private static final String POSTGRES_IMAGE =
            "postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2";

    @Container
    static final PostgreSQLContainer postgres =
            new PostgreSQLContainer(
                    DockerImageName.parse(POSTGRES_IMAGE).asCompatibleSubstituteFor("postgres"));

    @Test
    void linkRemainsAvailableAfterApplicationRestart() {
        String code;
        try (ConfigurableApplicationContext first = startApplication()) {
            code =
                    first.getBean(LinkService.class)
                            .create("https://example.com/persisted")
                            .getShortCode();
        }
        try (ConfigurableApplicationContext restarted = startApplication()) {
            assertThat(restarted.getBean(LinkService.class).findByCode(code).getUrl())
                    .isEqualTo("https://example.com/persisted");
        }
    }

    private ConfigurableApplicationContext startApplication() {
        return new SpringApplicationBuilder(UrlShortenerApplication.class)
                .properties("spring.main.web-application-type=none")
                .run(
                        "--spring.datasource.url=" + postgres.getJdbcUrl(),
                        "--spring.datasource.username=" + postgres.getUsername(),
                        "--spring.datasource.password=" + postgres.getPassword());
    }
}
