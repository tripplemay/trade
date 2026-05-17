/**
 * Vitest setup for component tests.
 *
 * Pulls in @testing-library/jest-dom's matcher extensions
 * (`toBeInTheDocument`, `toHaveAttribute`, etc.) so chart wrapper
 * tests can assert DOM presence without re-implementing helpers.
 *
 * Loaded by all tests via setupFiles in vitest.config.ts; tests that
 * run in node env (safety + non-component unit) ignore it because
 * jest-dom matchers register globally without side effects.
 */
import "@testing-library/jest-dom/vitest";
