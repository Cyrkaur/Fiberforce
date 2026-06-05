"""
Peak Force Calculator implementation.

This module provides the logic for calculating the peak muscle force
required from specific muscle regions at a static position during a lift.

Current scope (massive phase v0.2/0.3):
- Peak force only (static position)
- Uses moment arms stored in MuscleAttachment
- Simplified model: F_muscle ≈ Torque_at_joint / moment_arm
- Improved length-tension using MuscleArchitecture when available (PCSA, pennation, optimal fiber length)
- Basic multi-joint notes
"""

from typing import Optional
import math

from fiberforce.models import (
    AnalyzedPosition,
    ExternalLoad,
    MuscleForceResult,
    MuscleRegion,
    Subject,
)

from .base import BaseCalculator, CalculationContext


class SimplePeakForceCalculator(BaseCalculator):
    """
    A simplified but extensible peak force calculator.

    Core math (statics, per joint):
      external_joint_torque = load * load_moment_arm (at the joint)
      for each muscle attachment on that joint:
        raw_F = external_torque / muscle_MA
        peak_F = raw_F * LT_factor(angle) * FV_factor(v=0)
      Then, for co-movers on the *same* joint, we partition the joint torque
      using relative MA (dominance = MA_i / sum_MA):
        torque_share_i = (MA_i / sum_MA) * external_joint_torque
        (force is scaled to be consistent with the share)
      Sum of per-muscle torque_shares = joint external torque (no double-counting).

    This means different muscles on the same joint (pec vs ant delt on shoulder
    for bench) now report *different* peak_torque_ftlb (their shares) instead of
    all showing the full joint torque. The % dominance directly corresponds to
    the fraction of the reported joint torque "credited" to that muscle.
    Larger MA -> higher share of torque, lower force if it were sole contributor.

    Assumptions (documented for transparency):
    - Single-joint approximation per attachment (multi-joint muscles note only).
    - MA-proportional torque partitioning among co-prime-movers (simple model;
      real force sharing also depends on PCSA, pennation, activation patterns,
      optimization criteria like min stress or fatigue, etc.).
    - LT from architecture if provided, else ~1.0 plateau; FV=1.0 at v=0 (isometric).
    - See LIMITATIONS.md, how-the-model-works.md, and result notes for caveats.
    - "force number" in UI (ft-lb) is now the muscle's modeled torque contribution
      (share), not the full joint torque.
    """

    def calculate_peak_force(
        self,
        subject: Subject,
        position: AnalyzedPosition,
        context: "Optional[CalculationContext]" = None,
    ) -> list[MuscleForceResult]:
        try:
            self._validate_inputs(subject, position)
        except ValueError as e:
            # Return a graceful error result instead of crashing
            fallback_region = position.target_regions[0] if position.target_regions else MuscleRegion("Unknown", "Unknown")
            return [
                MuscleForceResult(
                    muscle_region=fallback_region,
                    peak_force_newtons=0.0,
                    confidence_level="error",
                    notes=f"Validation failed: {str(e)}",
                )
            ]

        _ = context or self.context  # reserved for future use

        results: list[MuscleForceResult] = []

        # Support multi-joint / multi-muscle: compute external torque per attachment's joint
        # Group for dominance % (larger MA = higher mechanical dominance at the joint)
        from collections import defaultdict
        joint_mas = defaultdict(list)  # joint -> [(result, ma_cm)]

        for region in position.target_regions:
            attachment = position.pose.get_attachment_for_region(region)

            if attachment is None:
                results.append(
                    MuscleForceResult(
                        muscle_region=region,
                        peak_force_newtons=0.0,
                        peak_torque_nm=None,
                        joint="unknown",
                        position_description=position.pose.describe(),
                        confidence_level="insufficient_data",
                        notes="No MuscleAttachment with moment arm data found for this region at the given pose.",
                    )
                )
                continue

            joint = attachment.joints_crossed[0] if attachment.joints_crossed else self._determine_primary_joint(position)
            external_torque, used_default_ma = self._estimate_external_torque(
                position.pose.external_load, joint, position
            )

            moment_arm = attachment.moment_arms_at_position.get(joint)

            if moment_arm is None or moment_arm <= 0:
                results.append(
                    MuscleForceResult(
                        muscle_region=region,
                        peak_force_newtons=0.0,
                        peak_torque_nm=external_torque,
                        joint=joint,
                        position_description=position.pose.describe(),
                        confidence_level="insufficient_data",
                        notes=f"No valid moment arm found for joint '{joint}'",
                    )
                )
                continue

            # Core physics (units fixed in 0.6):
            moment_arm_m = moment_arm / 100.0
            raw_force = external_torque / moment_arm_m

            # Theme 1 modeling...
            arch_key = f"{region.muscle_name.lower().replace(' ', '_')}_{region.region_name.lower().replace(' ', '_')}"
            arch_data = subject.anthropometry.muscle_architecture.get(arch_key, {})
            angle = position.pose.joint_angles.values.get(attachment.joints_crossed[0], 90.0) if attachment.joints_crossed else 90.0
            length_tension_factor, lt_data_used = self._compute_length_tension_factor(arch_data, angle)
            fv_factor = self._force_velocity_multiplier(0.0)
            peak_force = raw_force * length_tension_factor * fv_factor

            notes = f"Single-joint approximation. Length-tension factor: {length_tension_factor:.2f}."
            if lt_data_used:
                notes += " (architecture data used)"
            notes += f" F-V (v=0): {fv_factor:.2f}."
            notes += " "
            if len(attachment.joints_crossed) > 1:
                notes += "Attachment crosses multiple joints — torque sharing not modeled. "
            if used_default_ma:
                notes += "Load moment arm was defaulted (no Pose data provided for this joint). "
            if attachment and getattr(attachment, "notes", None):
                notes += " " + attachment.notes

            if used_default_ma:
                conf = "low (defaults used)"
            elif "reference" in (attachment.notes or "").lower() or "default" in (attachment.notes or "").lower():
                conf = "medium (reference data)"
            else:
                conf = "high (user-influenced)"

            res = MuscleForceResult(
                muscle_region=region,
                peak_force_newtons=round(peak_force, 2),
                peak_torque_nm=round(external_torque, 2),
                joint=joint,
                position_description=position.pose.describe(),
                confidence_level=conf,
                moment_arm_used_cm=moment_arm,
                notes=notes.strip(),
            )
            results.append(res)
            joint_mas[joint].append((res, moment_arm))

        # Compute dominance % per joint based on relative MA (larger MA = higher % dominance)
        # AND set per-muscle torque contribution (share of joint torque) so different muscles
        # on the same joint (e.g. pec vs ant delt on shoulder for bench) report *different*
        # peak_torque_ftlb values instead of all showing the full joint torque.
        # torque_share_i = (MA_i / sum) * external_joint_torque
        # Force scaled for consistency: effective F now produces exactly the share torque.
        # Sum of reported per-muscle torques across co-movers now equals the joint external torque.
        # This is the MA-proportional torque partitioning model (larger MA muscle gets larger
        # share of the "credit"/torque, requires lower force if acting alone).
        # See class docstring, _estimate..., and LIMITATIONS.md for full assumptions and literature.
        for j, items in joint_mas.items():
            total_ma = sum(ma for _, ma in items)
            if total_ma > 0:
                external = items[0][0].peak_torque_nm if items else 0.0
                for res, ma in items:
                    dom = round((ma / total_ma) * 100, 1)
                    res.dominance_percent = dom
                    share = (ma / total_ma) * external
                    res.peak_torque_nm = round(share, 2)
                    # Scale the already-computed force (which used full torque) down to the share fraction
                    if external > 0 and getattr(res, "peak_force_newtons", 0):
                        scale = ma / total_ma
                        res.peak_force_newtons = round(res.peak_force_newtons * scale, 2)
                    # Clarify notes
                    share_note = f"Modeled torque contribution/share: {dom:.1f}% of joint (MA-proportional). "
                    if share_note not in (res.notes or ""):
                        res.notes = share_note + (res.notes or "")

        return results

    def _determine_primary_joint(self, position: AnalyzedPosition) -> str:
        """
        Smarter heuristic:
        - Prefer the joint that appears in the most active attachments for the current targets.
        - Fall back to first joint of first attachment.
        - This works much better across bench (shoulder) vs squat (hip/knee).
        """
        if not position.pose.active_attachments:
            return "unknown"

        from collections import Counter
        joint_counts: Counter[str] = Counter()
        for att in position.pose.active_attachments:
            for j in att.joints_crossed:
                joint_counts[j] += 1

        if joint_counts:
            return joint_counts.most_common(1)[0][0]

        first_attachment = position.pose.active_attachments[0]
        if first_attachment.joints_crossed:
            return first_attachment.joints_crossed[0]

        return "unknown"

    def _estimate_external_torque(
        self,
        external_load: "Optional[ExternalLoad]",
        joint: str,
        position: AnalyzedPosition,
    ) -> tuple[float, bool]:
        """
        Estimate the external torque at a given joint caused by the external load.

        Returns:
            (torque_nm, used_default_load_moment_arm)

        Priority order for load moment arm:
        1. Data explicitly provided on the Pose (`load_moment_arms`)
        2. Fall back to a conservative default (with clear warning in result notes)
        """
        if external_load is None or external_load.mass_kg <= 0:
            return 0.0, False

        from fiberforce.calculations.utils import estimate_joint_torque_from_load

        load_moment_arm_cm = position.pose.get_load_moment_arm(joint)
        used_default = False

        if load_moment_arm_cm is None or load_moment_arm_cm <= 0:
            # Known limitation — we pick a plausible default per joint family
            if joint in ("hip", "knee"):
                load_moment_arm_cm = 20.0
            else:
                load_moment_arm_cm = 32.0
            used_default = True

        torque = estimate_joint_torque_from_load(external_load, load_moment_arm_cm)
        return torque, used_default

    def _compute_length_tension_factor(self, arch_data: dict, joint_angle_deg: float) -> tuple[float, bool]:
        """
        Improved length-tension (Theme 1 modeling depth start).

        Uses MuscleArchitecture data when present:
          optimal_fiber_length_cm, pennation_angle_deg, tendon_slack_length_cm, pcsa_cm2

        Computes a normalized fiber length (l/l0) using a simple excursion model
        (delta from angle * rough "fiber excursion per degree" proxy derived from opt_len).
        Then applies a standard active + passive force-length curve.

        Active: roughly plateau ~0.9-1.1 l0, linear ascending below, descending above
        (inspired by Gordon et al. 1966 and common OpenSim/Hatze approximations; not subject-specific).

        Passive: exponential-like rise beyond ~1.2 l0.

        Pennation reduces effective along-fiber length (cos(penn)).

        Returns (combined_factor 0.0-~1.2, data_used: bool).

        If no usable architecture data, returns conservative (0.82, False) — the old default.
        """
        opt_len = arch_data.get("optimal_fiber_length_cm")
        penn = arch_data.get("pennation_angle_deg", 0.0)
        tendon_slack = arch_data.get("tendon_slack_length_cm", 0.0)
        pcsa = arch_data.get("pcsa_cm2")

        if opt_len is None or opt_len <= 0:
            return 0.82, False

        # Effective fiber length accounting for pennation (fibers pull at angle)
        cos_penn = max(0.2, math.cos(math.radians(penn))) if penn else 1.0
        l0_eff = opt_len * cos_penn

        # Very rough fiber length change with joint angle.
        # In a real model this would come from the full kinematic chain + instantaneous MA.
        # Here we use a small excursion (cm per degree) scaled by l0 so it's relative.
        # ~0.008-0.015 l0 per degree is a typical order for many muscles around mid-ROM.
        excursion_per_deg = l0_eff * 0.012
        # Reference "neutral" at 90 deg (common for many single-joint calcs); real neutral varies.
        delta_cm = (joint_angle_deg - 90.0) * excursion_per_deg
        # Small additional from tendon compliance (very approximate)
        delta_cm += tendon_slack * 0.03

        l = l0_eff + delta_cm
        l_norm = l / l0_eff

        # --- Active force-length (piecewise approximation) ---
        if l_norm <= 0.5:
            active = 0.0
        elif l_norm < 0.9:
            active = (l_norm - 0.5) / 0.4   # ascending limb
        elif l_norm <= 1.1:
            active = 1.0                    # plateau
        elif l_norm < 1.6:
            active = max(0.0, 1.0 - (l_norm - 1.1) / 0.5)  # descending limb
        else:
            active = 0.0

        # --- Passive force-length (titin/extracellular, rises beyond ~1.2 l0) ---
        if l_norm > 1.2:
            passive = 0.05 * ((l_norm - 1.2) ** 2)   # gentle quadratic start
        else:
            passive = 0.0

        factor = active + passive

        # Mild penalty for very small PCSA (less "stiff" or lower quality tissue proxy)
        if pcsa is not None and pcsa < 4.0:
            factor *= 0.96

        # Clamp to physiologically reasonable range for peak isometric
        factor = max(0.0, min(1.25, factor))

        return round(factor, 3), True

    def _force_velocity_multiplier(self, velocity: float, v_max: float = 10.0) -> float:
        """
        Very basic Hill-type force-velocity (Theme 1 start).

        velocity: fiber shortening velocity (cm/s or consistent units). Positive = concentric.
        v_max: rough max shortening velocity (fiber lengths / sec scaled).

        For current static peak-force analyses we always pass v=0 -> 1.0 (isometric).
        Eccentric (negative v) simplified to ~1.0-1.2 (not boosting peak here).

        Returns multiplier ~0.1 .. 1.2 .
        """
        if velocity <= 0:
            # isometric or eccentric (we keep conservative for "peak" calc)
            return 1.0

        # Simple concentric approximation
        # (Vmax - v) / (Vmax + k*v) with k~3-4 typical
        k = 3.0
        mult = (v_max - velocity) / (v_max + k * velocity)
        return max(0.05, min(1.0, mult))