package com.schwab.urlshortener.persistence;

import com.schwab.urlshortener.domain.Link;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface LinkRepository extends JpaRepository<Link, UUID> {
    Optional<Link> findByShortCode(String shortCode);
}
