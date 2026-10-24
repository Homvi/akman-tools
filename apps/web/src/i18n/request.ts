import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;

  return {
    locale,
    // Keep SSR + client formatting aligned (avoids hydration text mismatches).
    timeZone: "Europe/Budapest",
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
