/**
 * Backend API types.
 *
 * B020: this file is a hand-authored stub limited to the `/health` response.
 * B020 F004 introduces `scripts/generate-types.sh` which regenerates this file
 * from the live backend OpenAPI schema; after F004 lands every entry here is
 * machine-generated and the CI drift check enforces parity.
 */

export interface HealthResponse {
  status: string;
  version: string;
}
