import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import {
  defaultLocale,
  isAppLocale,
  localeCookieName,
} from "@/core/i18n/config";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get(localeCookieName)?.value;
  const locale = isAppLocale(cookieLocale) ? cookieLocale : defaultLocale;

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
