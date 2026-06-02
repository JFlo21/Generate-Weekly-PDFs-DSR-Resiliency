import '@testing-library/jest-dom';
import { toHaveNoViolations } from 'jest-axe';   // D-07: WCAG a11y matcher
// Note: jsdom silently disables the axe color-contrast rule — contrast
// validation is the MANUAL UAT pass (D-07 second pass), not jest-axe.
expect.extend(toHaveNoViolations);               // D-07
