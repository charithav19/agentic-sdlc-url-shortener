package com.schwab.urlshortener.api;

import com.schwab.urlshortener.application.CollisionExhaustedException;
import com.schwab.urlshortener.application.InvalidExpiryException;
import com.schwab.urlshortener.application.InvalidIdempotencyKeyException;
import com.schwab.urlshortener.application.LinkConflictException;
import com.schwab.urlshortener.application.LinkGoneException;
import com.schwab.urlshortener.application.LinkNotFoundException;
import com.schwab.urlshortener.domain.InvalidAliasException;
import com.schwab.urlshortener.domain.InvalidUrlException;
import com.schwab.urlshortener.observability.TraceIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(LinkNotFoundException.class)
    ResponseEntity<ApiError> notFound(LinkNotFoundException exception, HttpServletRequest request) {
        return error(
                HttpStatus.NOT_FOUND, "LINK_NOT_FOUND", exception.getMessage(), List.of(), request);
    }

    @ExceptionHandler(InvalidUrlException.class)
    ResponseEntity<ApiError> invalidUrl(InvalidUrlException exception, HttpServletRequest request) {
        return error(
                HttpStatus.BAD_REQUEST, "INVALID_URL", exception.getMessage(), List.of(), request);
    }

    @ExceptionHandler(InvalidAliasException.class)
    ResponseEntity<ApiError> invalidAlias(
            InvalidAliasException exception, HttpServletRequest request) {
        return error(
                HttpStatus.BAD_REQUEST,
                "INVALID_ALIAS",
                exception.getMessage(),
                List.of(),
                request);
    }

    @ExceptionHandler(InvalidExpiryException.class)
    ResponseEntity<ApiError> invalidExpiry(
            InvalidExpiryException exception, HttpServletRequest request) {
        return error(
                HttpStatus.BAD_REQUEST,
                "INVALID_EXPIRY",
                exception.getMessage(),
                List.of(),
                request);
    }

    @ExceptionHandler(InvalidIdempotencyKeyException.class)
    ResponseEntity<ApiError> invalidIdempotencyKey(
            InvalidIdempotencyKeyException exception, HttpServletRequest request) {
        return error(
                HttpStatus.BAD_REQUEST,
                "INVALID_IDEMPOTENCY_KEY",
                exception.getMessage(),
                List.of(),
                request);
    }

    @ExceptionHandler(LinkConflictException.class)
    ResponseEntity<ApiError> conflict(LinkConflictException exception, HttpServletRequest request) {
        return error(
                HttpStatus.CONFLICT,
                exception.getCode(),
                exception.getMessage(),
                List.of(),
                request);
    }

    @ExceptionHandler(LinkGoneException.class)
    ResponseEntity<ApiError> gone(LinkGoneException exception, HttpServletRequest request) {
        return error(HttpStatus.GONE, "LINK_GONE", exception.getMessage(), List.of(), request);
    }

    @ExceptionHandler(CollisionExhaustedException.class)
    ResponseEntity<ApiError> exhausted(
            CollisionExhaustedException exception, HttpServletRequest request) {
        return error(
                HttpStatus.SERVICE_UNAVAILABLE,
                "CODE_ALLOCATION_EXHAUSTED",
                exception.getMessage(),
                List.of(),
                request);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> validation(
            MethodArgumentNotValidException exception, HttpServletRequest request) {
        List<ApiError.Detail> details =
                exception.getBindingResult().getFieldErrors().stream()
                        .map(
                                field ->
                                        new ApiError.Detail(
                                                field.getField(), field.getDefaultMessage()))
                        .toList();
        return error(
                HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "Invalid request", details, request);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<ApiError> unreadable(
            HttpMessageNotReadableException exception, HttpServletRequest request) {
        return error(
                HttpStatus.BAD_REQUEST,
                "INVALID_REQUEST",
                "Invalid JSON request body",
                List.of(),
                request);
    }

    @ExceptionHandler({NoHandlerFoundException.class, NoResourceFoundException.class})
    ResponseEntity<ApiError> unmappedPath(Exception exception, HttpServletRequest request) {
        return error(HttpStatus.NOT_FOUND, "PATH_NOT_FOUND", "Path not found", List.of(), request);
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> unexpected(Exception exception, HttpServletRequest request) {
        return error(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Unexpected server error",
                List.of(),
                request);
    }

    private ResponseEntity<ApiError> error(
            HttpStatus status,
            String code,
            String message,
            List<ApiError.Detail> details,
            HttpServletRequest request) {
        Object trace = request.getAttribute(TraceIdFilter.TRACE_ID_ATTRIBUTE);
        String traceId = trace instanceof String value ? value : UUID.randomUUID().toString();
        return ResponseEntity.status(status).body(new ApiError(code, message, traceId, details));
    }
}
