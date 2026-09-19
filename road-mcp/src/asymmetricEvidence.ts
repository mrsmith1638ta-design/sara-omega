import {
  createHash,
  createPublicKey,
  verify as cryptoVerify,
} from "node:crypto";

export type SaraAsymmetricAlgorithm = "Ed25519" | "ML-DSA";

export interface RoadVerificationKey {
  algorithm: SaraAsymmetricAlgorithm;
  keyId: string;
  publicKeyPem: string;
  publicKeySha256: string;
}

export interface SignedDigest {
  algorithm: SaraAsymmetricAlgorithm;
  keyId: string;
  digestB64: string;
  signatureB64: string;
}

export interface VerificationResult {
  verified: boolean;
  reason: string;
  keyFingerprint: string | null;
}

function decodeBase64Strict(value: string, field: string): Buffer {
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(value) || value.length % 4 !== 0) {
    throw new Error(field + "_invalid_base64");
  }
  const decoded = Buffer.from(value, "base64");
  if (decoded.length === 0 || decoded.toString("base64") !== value) {
    throw new Error(field + "_invalid_base64");
  }
  return decoded;
}

export function publicKeyFingerprint(publicKeyPem: string): string {
  const key = createPublicKey(publicKeyPem);
  const der = key.export({ format: "der", type: "spki" });
  return createHash("sha256").update(der).digest("hex");
}

export function verifySaraKmsSignature(
  signed: SignedDigest,
  verificationKey: RoadVerificationKey,
): VerificationResult {
  if (signed.algorithm !== verificationKey.algorithm) {
    return { verified: false, reason: "algorithm_mismatch", keyFingerprint: null };
  }
  if (signed.keyId !== verificationKey.keyId) {
    return { verified: false, reason: "key_id_mismatch", keyFingerprint: null };
  }

  let key;
  let fingerprint: string;
  let digest: Buffer;
  let signature: Buffer;
  try {
    key = createPublicKey(verificationKey.publicKeyPem);
    fingerprint = publicKeyFingerprint(verificationKey.publicKeyPem);
    digest = decodeBase64Strict(signed.digestB64, "digest");
    signature = decodeBase64Strict(signed.signatureB64, "signature");
  } catch {
    return { verified: false, reason: "invalid_verification_material", keyFingerprint: null };
  }

  if (digest.length !== 64) {
    return { verified: false, reason: "digest_length_mismatch", keyFingerprint: fingerprint };
  }
  if (fingerprint !== verificationKey.publicKeySha256.toLowerCase()) {
    return { verified: false, reason: "public_key_fingerprint_mismatch", keyFingerprint: fingerprint };
  }

  const expectedType = signed.algorithm === "Ed25519" ? "ed25519" : "ml-dsa-65";
  if (key.asymmetricKeyType !== expectedType) {
    return { verified: false, reason: "public_key_type_mismatch", keyFingerprint: fingerprint };
  }

  try {
    const verified = cryptoVerify(null, digest, key, signature);
    return {
      verified,
      reason: verified ? "signature_valid" : "signature_invalid",
      keyFingerprint: fingerprint,
    };
  } catch {
    return { verified: false, reason: "signature_verification_error", keyFingerprint: fingerprint };
  }
}

export function verifySaraDualKmsSignatures(
  signed: readonly SignedDigest[],
  keys: readonly RoadVerificationKey[],
): {
  verified: boolean;
  results: Record<SaraAsymmetricAlgorithm, VerificationResult>;
} {
  const algorithms: readonly SaraAsymmetricAlgorithm[] = ["Ed25519", "ML-DSA"];
  const results = {} as Record<SaraAsymmetricAlgorithm, VerificationResult>;

  for (const algorithm of algorithms) {
    const signature = signed.find((entry) => entry.algorithm === algorithm);
    const key = keys.find((entry) => entry.algorithm === algorithm);
    if (!signature || !key) {
      results[algorithm] = {
        verified: false,
        reason: !signature ? "signature_missing" : "verification_key_missing",
        keyFingerprint: null,
      };
      continue;
    }
    results[algorithm] = verifySaraKmsSignature(signature, key);
  }

  return {
    verified: algorithms.every((algorithm) => results[algorithm].verified),
    results,
  };
}

function envRequired(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name]?.trim();
  if (!value) throw new Error(name + "_required");
  return value;
}

function pemFromBase64(value: string): string {
  const decoded = Buffer.from(value, "base64").toString("utf8");
  if (!decoded.includes("BEGIN PUBLIC KEY")) throw new Error("public_key_pem_invalid");
  return decoded;
}

export function loadPinnedSaraVerificationKeys(
  env: NodeJS.ProcessEnv = process.env,
): RoadVerificationKey[] {
  return [
    {
      algorithm: "Ed25519",
      keyId: envRequired(env, "ROAD_SARA_ED25519_KEY_ID"),
      publicKeyPem: pemFromBase64(envRequired(env, "ROAD_SARA_ED25519_PUBLIC_KEY_B64")),
      publicKeySha256: envRequired(env, "ROAD_SARA_ED25519_PUBLIC_KEY_SHA256").toLowerCase(),
    },
    {
      algorithm: "ML-DSA",
      keyId: envRequired(env, "ROAD_SARA_ML_DSA_KEY_ID"),
      publicKeyPem: pemFromBase64(envRequired(env, "ROAD_SARA_ML_DSA_PUBLIC_KEY_B64")),
      publicKeySha256: envRequired(env, "ROAD_SARA_ML_DSA_PUBLIC_KEY_SHA256").toLowerCase(),
    },
  ];
}

