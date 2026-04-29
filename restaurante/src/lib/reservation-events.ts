import { EventEmitter } from "node:events";

export const reservationEvents = new EventEmitter();
reservationEvents.setMaxListeners(200);

export function notifyReservationChange() {
  reservationEvents.emit("update");
}
