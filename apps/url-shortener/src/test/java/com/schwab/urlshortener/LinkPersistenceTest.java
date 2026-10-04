package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.schwab.urlshortener.domain.Link;
import com.schwab.urlshortener.persistence.LinkRepository;
import jakarta.persistence.EntityManager;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class LinkPersistenceTest {
    private static final String POSTGRES_IMAGE =
            "postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2";

    @Container
    static final PostgreSQLContainer postgres =
            new PostgreSQLContainer(
                    DockerImageName.parse(POSTGRES_IMAGE).asCompatibleSubstituteFor("postgres"));

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired private LinkRepository links;
    @Autowired private EntityManager entities;
    @Autowired private JdbcTemplate jdbc;

    @Test
    void flywayMigrationCreatedTheRequiredSchema() {
        Integer migrations =
                jdbc.queryForObject(
                        "SELECT count(*) FROM flyway_schema_history WHERE version = '1' AND success",
                        Integer.class);
        assertThat(migrations).isEqualTo(1);
        assertThat(
                        jdbc.queryForObject(
                                "SELECT count(*) FROM flyway_schema_history WHERE version = '2' AND success",
                                Integer.class))
                .isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM links", Integer.class)).isNotNull();
    }

    @Test
    void linkSurvivesPersistenceContextClear() {
        Link created =
                links.saveAndFlush(
                        new Link(
                                "Aa01234",
                                "https://example.com/article",
                                Instant.parse("2026-10-04T12:00:00Z")));
        entities.clear();
        Link fetched = links.findByShortCode("Aa01234").orElseThrow();
        assertThat(fetched.getId()).isEqualTo(created.getId());
        assertThat(fetched.getUrl()).isEqualTo("https://example.com/article");
        assertThat(fetched.getCreatedAt()).isEqualTo(Instant.parse("2026-10-04T12:00:00Z"));
    }

    @Test
    void databaseRejectsDuplicateShortCodes() {
        links.saveAndFlush(new Link("Cc56789", "https://example.com/first", Instant.now()));
        assertThatThrownBy(
                        () ->
                                links.saveAndFlush(
                                        new Link(
                                                "Cc56789",
                                                "https://example.com/second",
                                                Instant.now())))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
