package com.schwab.urlshortener.analytics;

import com.schwab.urlshortener.api.AnalyticsResponse;
import com.schwab.urlshortener.application.LinkService;
import com.schwab.urlshortener.domain.Link;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AnalyticsService {
    private final LinkService links;
    private final JdbcTemplate jdbc;

    public AnalyticsService(LinkService links, JdbcTemplate jdbc) {
        this.links = links;
        this.jdbc = jdbc;
    }

    @Transactional(readOnly = true)
    public AnalyticsResponse forCode(String shortCode) {
        Link link = links.findByCode(shortCode);
        Map<String, Long> byDay = new LinkedHashMap<>();
        jdbc.query(
                """
                SELECT (occurred_at AT TIME ZONE 'UTC')::date AS day, count(*) AS clicks
                FROM click_events
                WHERE link_id = ?
                GROUP BY (occurred_at AT TIME ZONE 'UTC')::date
                ORDER BY day
                """,
                result -> {
                    byDay.put(
                            result.getDate("day").toLocalDate().toString(),
                            result.getLong("clicks"));
                },
                link.getId());
        long total = byDay.values().stream().mapToLong(Long::longValue).sum();
        return new AnalyticsResponse(shortCode, total, byDay);
    }
}
