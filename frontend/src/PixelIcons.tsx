import type { CSSProperties } from "react";
import pixelHeart from "./assets/pixel-heart.png";
import pixelStethoscope from "./assets/pixel-stethoscope.png";

export { pixelHeart, pixelStethoscope };

interface PixelIconProps {
  size?: number;
  className?: string;
  style?: CSSProperties;
  color?: string;
}

const basePixelStyle: CSSProperties = {
  imageRendering: "pixelated",
  display: "inline-block",
  verticalAlign: "middle",
  flexShrink: 0,
};

/** Workspace Persona Icons (High-res pixel art assets from landing page) */
export function PixelWorkspaceIcon({
  workspace,
  size = 20,
  className = "",
  style,
}: {
  workspace: "patient" | "doctor";
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const src = workspace === "patient" ? pixelHeart : pixelStethoscope;

  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      className={`pixel-art-inline pixel-workspace-icon-${workspace} ${className}`.trim()}
      style={{
        ...basePixelStyle,
        width: size,
        height: size,
        objectFit: "contain",
        ...style,
      }}
    />
  );
}

/** Pixel Sun for Light appearance switch */
export function PixelSun({
  size = 18,
  className = "",
  style,
  color = "currentColor",
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      fill={color}
      className={`pixel-svg ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Center core */}
      <rect x="5" y="5" width="6" height="6" />
      {/* Cardinal rays */}
      <rect x="7" y="1" width="2" height="3" />
      <rect x="7" y="12" width="2" height="3" />
      <rect x="1" y="7" width="3" height="2" />
      <rect x="12" y="7" width="3" height="2" />
      {/* Diagonal rays */}
      <rect x="3" y="3" width="2" height="2" />
      <rect x="11" y="3" width="2" height="2" />
      <rect x="3" y="11" width="2" height="2" />
      <rect x="11" y="11" width="2" height="2" />
    </svg>
  );
}

/** Pixel Crescent Moon for Dark appearance switch */
export function PixelMoon({
  size = 18,
  className = "",
  style,
  color = "currentColor",
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      fill={color}
      className={`pixel-svg ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <rect x="6" y="2" width="4" height="2" />
      <rect x="4" y="4" width="3" height="2" />
      <rect x="3" y="6" width="3" height="4" />
      <rect x="4" y="10" width="3" height="2" />
      <rect x="6" y="12" width="4" height="2" />
      <rect x="10" y="11" width="2" height="2" />
      <rect x="9" y="8" width="2" height="3" />
      <rect x="10" y="3" width="2" height="2" />
      <rect x="11" y="2" width="1" height="1" />
      <rect x="11" y="13" width="1" height="1" />
    </svg>
  );
}

/** Combined Theme Switcher Icon */
export function PixelThemeToggle({
  dark,
  size = 18,
}: {
  dark: boolean;
  size?: number;
}) {
  return dark ? <PixelSun size={size} /> : <PixelMoon size={size} />;
}

/** Pixel Pill / Medications */
export function PixelPill({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-pill ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Top half (Accent / Primary color) */}
      <rect x="4" y="2" width="8" height="2" fill="var(--primary, #195941)" />
      <rect x="3" y="4" width="10" height="3" fill="var(--primary, #195941)" />
      {/* Separation divider line */}
      <rect
        x="3"
        y="7"
        width="10"
        height="2"
        fill="var(--ink, #1f2937)"
        opacity="0.3"
      />
      {/* Bottom half (Soft / Highlight color) */}
      <rect x="3" y="9" width="10" height="3" fill="var(--focus, #15803d)" />
      <rect x="4" y="12" width="8" height="2" fill="var(--focus, #15803d)" />
      {/* Pill reflection shine */}
      <rect x="5" y="4" width="2" height="2" fill="#ffffff" opacity="0.75" />
    </svg>
  );
}

/** Pixel Flask / Lab Tests */
export function PixelFlask({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-flask ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Neck & rim */}
      <rect x="6" y="2" width="4" height="1" fill="currentColor" />
      <rect x="7" y="3" width="2" height="4" fill="currentColor" />
      {/* Triangular flask outline */}
      <rect x="6" y="7" width="4" height="2" fill="currentColor" />
      <rect x="5" y="9" width="6" height="2" fill="currentColor" />
      <rect x="3" y="11" width="10" height="3" fill="var(--focus, #15803d)" />
      {/* Liquid bubbles */}
      <rect x="6" y="12" width="2" height="2" fill="#ffffff" opacity="0.8" />
      <rect x="10" y="11" width="1" height="1" fill="#ffffff" opacity="0.8" />
    </svg>
  );
}

/** Pixel Vitals / EKG Heartbeat Wave */
export function PixelVitals({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-vitals ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Baseline left */}
      <rect x="1" y="8" width="3" height="2" fill="currentColor" />
      {/* Q dip */}
      <rect x="4" y="9" width="1" height="2" fill="currentColor" />
      <rect x="5" y="10" width="1" height="2" fill="currentColor" />
      {/* R spike up */}
      <rect x="6" y="3" width="2" height="7" fill="var(--review, #e11d48)" />
      {/* S plunge down */}
      <rect x="8" y="10" width="2" height="4" fill="var(--review, #e11d48)" />
      {/* T wave */}
      <rect x="10" y="6" width="2" height="3" fill="currentColor" />
      {/* Baseline right */}
      <rect x="12" y="8" width="3" height="2" fill="currentColor" />
    </svg>
  );
}

/** Pixel Clinic / Visits */
export function PixelVisit({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-visit ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Roof cross */}
      <rect x="7" y="1" width="2" height="3" fill="var(--review, #dc2626)" />
      <rect x="6" y="2" width="4" height="1" fill="var(--review, #dc2626)" />
      {/* Building walls */}
      <rect x="2" y="4" width="12" height="11" fill="currentColor" />
      {/* Windows (soft/paper cutouts) */}
      <rect x="4" y="6" width="2" height="2" fill="var(--paper, #ffffff)" />
      <rect x="10" y="6" width="2" height="2" fill="var(--paper, #ffffff)" />
      {/* Doorway */}
      <rect x="7" y="11" width="2" height="4" fill="var(--paper, #ffffff)" />
    </svg>
  );
}

/** Pixel Shield / Allergies */
export function PixelShield({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-shield ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Shield outline */}
      <rect x="3" y="2" width="10" height="2" fill="var(--review, #e11d48)" />
      <rect x="2" y="4" width="12" height="5" fill="var(--review, #e11d48)" />
      <rect x="3" y="9" width="10" height="3" fill="var(--review, #e11d48)" />
      <rect x="5" y="12" width="6" height="2" fill="var(--review, #e11d48)" />
      <rect x="7" y="14" width="2" height="1" fill="var(--review, #e11d48)" />
      {/* Center exclamation */}
      <rect x="7" y="4" width="2" height="4" fill="#ffffff" />
      <rect x="7" y="9" width="2" height="2" fill="#ffffff" />
    </svg>
  );
}

/** Pixel Syringe / Immunizations */
export function PixelSyringe({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-syringe ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Plunger */}
      <rect x="12" y="2" width="2" height="2" fill="currentColor" />
      <rect x="10" y="4" width="3" height="2" fill="currentColor" />
      {/* Syringe barrel */}
      <rect x="6" y="6" width="5" height="5" fill="var(--focus, #15803d)" />
      {/* Barrel markings */}
      <rect x="7" y="7" width="1" height="1" fill="#ffffff" />
      <rect x="9" y="9" width="1" height="1" fill="#ffffff" />
      {/* Needle tip */}
      <rect x="4" y="11" width="2" height="2" fill="currentColor" />
      <rect x="2" y="13" width="2" height="2" fill="currentColor" />
    </svg>
  );
}

/** Pixel Clipboard / Documents & Care Plans */
export function PixelDocument({
  size = 18,
  className = "",
  style,
}: PixelIconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-doc ${className}`.trim()}
      style={{ ...basePixelStyle, ...style }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* Top clip */}
      <rect x="6" y="1" width="4" height="2" fill="currentColor" />
      {/* Board outline */}
      <rect x="3" y="3" width="10" height="12" fill="currentColor" />
      {/* Document content lines */}
      <rect x="5" y="6" width="6" height="1" fill="var(--bg)" />
      <rect x="5" y="8" width="6" height="1" fill="var(--bg)" />
      <rect x="5" y="10" width="4" height="1" fill="var(--bg)" />
    </svg>
  );
}

/** Pixel Verified Shield Badge */
export function PixelVerifiedShield({
  size = 14,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 14 14"
      width={size}
      height={size}
      className={`pixel-svg pixel-svg-verified ${className}`.trim()}
      style={{ ...basePixelStyle, marginRight: 4 }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <rect x="2" y="1" width="10" height="2" fill="#15803d" />
      <rect x="1" y="3" width="12" height="4" fill="#15803d" />
      <rect x="2" y="7" width="10" height="3" fill="#15803d" />
      <rect x="4" y="10" width="6" height="2" fill="#15803d" />
      <rect x="6" y="12" width="2" height="1" fill="#15803d" />
      {/* Checkmark inside */}
      <rect x="3" y="6" width="2" height="2" fill="#ffffff" />
      <rect x="5" y="7" width="2" height="2" fill="#ffffff" />
      <rect x="7" y="5" width="2" height="2" fill="#ffffff" />
      <rect x="9" y="3" width="2" height="2" fill="#ffffff" />
    </svg>
  );
}

/** Pixel Empty State Vignette Illustration */
export function PixelEmptyVignette({
  type = "records",
  size = 56,
}: {
  type?: "records" | "requests" | "inbox";
  size?: number;
}) {
  return (
    <div
      className="pixel-empty-vignette"
      aria-hidden="true"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 12,
      }}
    >
      {type === "records" ? (
        <svg
          viewBox="0 0 32 32"
          width={size}
          height={size}
          shapeRendering="crispEdges"
          style={basePixelStyle}
        >
          {/* Filing folder back */}
          <rect x="4" y="8" width="10" height="4" fill="var(--line, #cbd5e1)" />
          <rect
            x="4"
            y="10"
            width="24"
            height="16"
            fill="var(--soft, #e2e8f0)"
          />
          {/* Paper sheet */}
          <rect
            x="8"
            y="6"
            width="16"
            height="12"
            fill="var(--paper, #ffffff)"
          />
          <rect x="10" y="8" width="8" height="2" fill="var(--line, #cbd5e1)" />
          <rect
            x="10"
            y="11"
            width="10"
            height="2"
            fill="var(--line, #cbd5e1)"
          />
          {/* Folder front flap */}
          <rect
            x="4"
            y="14"
            width="24"
            height="13"
            fill="var(--primary, #195941)"
            opacity="0.85"
          />
          {/* Subtle magnifying glass */}
          <rect
            x="18"
            y="17"
            width="6"
            height="2"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="16"
            y="19"
            width="2"
            height="4"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="24"
            y="19"
            width="2"
            height="4"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="18"
            y="23"
            width="6"
            height="2"
            fill="var(--focus, #15803d)"
          />
          <rect x="24" y="24" width="4" height="4" fill="var(--ink, #111827)" />
        </svg>
      ) : (
        <svg
          viewBox="0 0 32 32"
          width={size}
          height={size}
          shapeRendering="crispEdges"
          style={basePixelStyle}
        >
          {/* Clipboard board */}
          <rect x="12" y="2" width="8" height="4" fill="var(--ink, #111827)" />
          <rect
            x="6"
            y="5"
            width="20"
            height="24"
            fill="var(--soft, #e2e8f0)"
          />
          {/* Paper inside */}
          <rect
            x="8"
            y="8"
            width="16"
            height="19"
            fill="var(--paper, #ffffff)"
          />
          {/* Green checkmark seal */}
          <rect
            x="14"
            y="14"
            width="8"
            height="8"
            fill="rgba(21, 128, 61, 0.15)"
          />
          <rect
            x="12"
            y="17"
            width="2"
            height="3"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="14"
            y="19"
            width="3"
            height="3"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="17"
            y="15"
            width="3"
            height="3"
            fill="var(--focus, #15803d)"
          />
          <rect
            x="20"
            y="12"
            width="3"
            height="3"
            fill="var(--focus, #15803d)"
          />
        </svg>
      )}
    </div>
  );
}
