package com.schwab.urlshortener.config;

import java.util.concurrent.ThreadPoolExecutor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
public class ManagementConfig {
    @Bean(name = "analyticsExecutor")
    ThreadPoolTaskExecutor analyticsExecutor(AnalyticsProperties properties) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(properties.maxThreads());
        executor.setMaxPoolSize(properties.maxThreads());
        executor.setQueueCapacity(properties.queueCapacity());
        executor.setThreadNamePrefix("analytics-writer-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.AbortPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(false);
        executor.setAwaitTerminationSeconds(2);
        executor.initialize();
        return executor;
    }
}
