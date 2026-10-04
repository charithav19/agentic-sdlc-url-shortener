package com.schwab.urlshortener.analytics;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ClickEventRepository extends JpaRepository<ClickEvent, UUID> {
    long countByLinkId(UUID linkId);
}
