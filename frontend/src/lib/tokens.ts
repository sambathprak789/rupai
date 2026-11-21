/**
 * Rough token count for the Qwen-Image 2.1 text encoder (Qwen2 BPE tokenizer).
 *
 * Weights were calibrated against the real tokenizer on 2026-11-21:
 *   English words + spaces  ≈ 4.5 chars per token
 *   digits / punctuation    ≈ 1.5 chars per token
 *   Khmer                   ≈ 1.25 tokens per char (Khmer is ~5× more expensive than English)
 *   anything else           ≈ 1 token per char
 * Typical error is ±25%, which is enough for a "~N tokens" hint.
 */
const KHMER = /[ក-៿᧠-᧿]/g
const WORD = /[A-Za-z ]/g
const ASCII = /[\u0020-\u007E\t\n\r]/g

export function estimateTokens(text: string): number {
  if (!text) return 0
  const khmer = text.match(KHMER)?.length ?? 0
  const word = text.match(WORD)?.length ?? 0
  const otherAscii = (text.match(ASCII)?.length ?? 0) - word
  const other = text.length - khmer - word - otherAscii
  return Math.round(word / 4.5 + otherAscii / 1.5 + khmer * 1.25 + other)
}
