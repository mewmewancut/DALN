import { errorMessage } from "../api/errorMessage.js";

export function cartErrorMessage(failure) {
  if (failure instanceof Error && !failure.isAxiosError) return failure.message;
  return errorMessage(failure);
}
