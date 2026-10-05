package com.schwab.urlshortener.api;

import com.schwab.urlshortener.application.RedirectService;
import io.swagger.v3.oas.annotations.Operation;
import java.net.URI;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RedirectController {
    private final RedirectService service;

    public RedirectController(RedirectService service) {
        this.service = service;
    }

    @Operation(summary = "Redirect a known short code")
    @GetMapping("/{shortCode}")
    public ResponseEntity<Void> redirect(@PathVariable String shortCode) {
        var link = service.resolve(shortCode);
        return ResponseEntity.status(HttpStatus.FOUND)
                .location(URI.create(link.getOriginalUrl()))
                .build();
    }
}
