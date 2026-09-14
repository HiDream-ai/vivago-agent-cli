"use strict";

const { PROFILE } = require("./config");

const PAYMENT_REASON_BY_CODE = Object.freeze({
  2007: "credits",
  2020: "membership",
});
const PAYMENT_REASON_BY_NAME = Object.freeze({
  insufficient_credits: "credits",
  trade_no_credits_available: "credits",
});

function paymentRequirementFromEvent(event) {
  const payload = event && event.data && typeof event.data === "object"
    ? event.data
    : {};
  const nested = payload.data && typeof payload.data === "object"
    ? payload.data
    : {};
  const rawCode = payload.code ?? payload.error_code ?? nested.code ?? nested.error_code;
  const numericCode = Number(rawCode);
  const numericReason = PAYMENT_REASON_BY_CODE[numericCode];
  const normalizedCode = String(rawCode ?? "").trim().toLowerCase();
  const reason = numericReason ?? PAYMENT_REASON_BY_NAME[normalizedCode];
  if (!reason) {
    return null;
  }
  return {
    reason,
    code: numericReason ? numericCode : normalizedCode,
    url: PROFILE.paymentURLs[reason],
    return_url: PROFILE.paymentReturnURL,
  };
}

module.exports = { paymentRequirementFromEvent };
