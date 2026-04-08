export type ServiceHealth = {
  service: string;
  status: "ok" | "degraded" | "down";
};

export * from "./canonicalJson";
export * from "./contractVersions";
export * from "./drawing";
export * from "./gatewayReadEnvelope";
export * from "./eventStreams";
export * from "./eventEnvelope";
