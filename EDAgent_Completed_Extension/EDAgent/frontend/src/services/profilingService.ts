// Kept for import compatibility; the implementation lives in ./api.
import { profilingService as svc } from './api';
export const profilingService = { ...svc, triggerProfile: svc.rerun };
