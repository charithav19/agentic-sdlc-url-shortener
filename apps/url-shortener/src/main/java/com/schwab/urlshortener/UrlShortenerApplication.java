package com.schwab.urlshortener;

import com.schwab.urlshortener.config.AnalyticsProperties;
import com.schwab.urlshortener.config.RateLimitProperties;
import com.schwab.urlshortener.config.ShortUrlProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({
    ShortUrlProperties.class,
    RateLimitProperties.class,
    AnalyticsProperties.class
})
public class UrlShortenerApplication {
    public static void main(String[] args) {
        SpringApplication.run(UrlShortenerApplication.class, args);
    }
}
