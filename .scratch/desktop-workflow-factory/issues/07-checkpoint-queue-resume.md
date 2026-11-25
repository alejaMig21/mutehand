# 07: Checkpoints, tutor queue and resume

**What to build:** When the apprentice cannot continue (precondition not met, control not found, no consent, template no match) it stops that flow, leaves a doubt in the tutor queue with a structural capture (roles and counts only), and keeps independent flows running. When the doubt is answered, the stopped flow resumes from its last checkpoint.

**Blocked by:** 01, 03

**Status:** resolved

- [x] Each stop writes one doubt with node, lesson, reason, structural capture and status open
- [x] The structural capture contains no text content
- [x] An independent flow continues while another is stopped
- [x] Marking a doubt answered makes the stopped flow resumable from its last checkpoint
- [x] Doubt status moves only among open, answered and dismissed
