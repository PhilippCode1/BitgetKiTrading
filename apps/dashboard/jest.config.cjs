/** @type {import('jest').Config} */
module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.cjs"],
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.test.ts", "**/__tests__/**/*.test.tsx"],
  collectCoverageFrom: [
    "src/lib/operator-console.ts",
    "src/lib/operator-snapshot.ts",
    "src/lib/signal-rationale.ts",
    "src/lib/format.ts",
    "src/lib/sensitive-action-prompts.ts",
    "src/lib/console-access-policy.ts",
    "src/components/market/MarketCapabilityMatrixTable.tsx",
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 85,
      lines: 85,
      statements: 85,
    },
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
};
