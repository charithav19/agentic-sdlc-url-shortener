package com.schwab.urlshortener.analytics;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AnalyticsWriter {
    private final ClickEventRepository events;
    private final JdbcTemplate jdbc;

    public AnalyticsWriter(ClickEventRepository events, JdbcTemplate jdbc) {
        this.events = events;
        this.jdbc = jdbc;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, timeout = 2)
    public void persist(ClickEvent event) {
        jdbc.execute("SET LOCAL statement_timeout = '2000ms'");
        events.saveAndFlush(event);
    }
}
