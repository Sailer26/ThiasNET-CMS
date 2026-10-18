import { describe, expect, it as test } from "vitest";
import { placeFromLink, videoFromLink } from "./pasteLinks";

describe("incolla il link del video", () => {
  test.each([
    ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"],
    ["youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
  ])("YouTube: %s", (link, id) => expect(videoFromLink(link)).toEqual({ provider: "youtube", video_id: id }));

  test.each([
    ["https://vimeo.com/76979871", "76979871"],
    ["https://player.vimeo.com/video/76979871?h=abc", "76979871"],
    ["vimeo.com/channels/staffpicks/76979871", "76979871"],
  ])("Vimeo: %s", (link, id) => expect(videoFromLink(link)).toEqual({ provider: "vimeo", video_id: id }));

  test.each(["", "ciao", "https://www.youtube.com/watch?v=corto", "https://evil.example/watch?v=dQw4w9WgXcQ", "https://vimeo.com/abc"])(
    "non riconosciuto: %s",
    (link) => expect(videoFromLink(link)).toBeNull(),
  );
});

describe("incolla il link della mappa", () => {
  test("OpenStreetMap con #map", () => {
    expect(placeFromLink("https://www.openstreetmap.org/#map=17/46.00374/8.95107")).toEqual({ lat: 46.00374, lng: 8.95107, zoom: 17 });
  });
  test("OpenStreetMap con il segnaposto", () => {
    expect(placeFromLink("https://www.openstreetmap.org/?mlat=46.1&mlon=8.9#map=15/46.1/8.9")).toEqual({ lat: 46.1, lng: 8.9, zoom: 15 });
    expect(placeFromLink("https://www.openstreetmap.org/?mlat=46.1&mlon=8.9")).toEqual({ lat: 46.1, lng: 8.9 });
  });
  test("Google Maps", () => {
    expect(placeFromLink("https://www.google.com/maps/place/Lugano/@46.0036778,8.9510602,15z/data=x")).toEqual({
      lat: 46.003678, lng: 8.95106, zoom: 15,
    });
    expect(placeFromLink("https://www.google.com/maps/@46.0,8.9,25z")).toEqual({ lat: 46, lng: 8.9, zoom: 19 });
  });
  test("coordinate scritte a mano", () => {
    expect(placeFromLink(" 46.0037, 8.9511 ")).toEqual({ lat: 46.0037, lng: 8.9511 });
  });
  test.each(["", "Lugano", "91, 8", "46, 181", "https://www.openstreetmap.org/"])("non riconosciuto: %s", (text) =>
    expect(placeFromLink(text)).toBeNull(),
  );
});
