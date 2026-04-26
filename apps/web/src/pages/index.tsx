import { useEffect } from "react";
import { useRouter } from "next/router";

export default function IndexRedirect() {
  const router = useRouter();

  useEffect(() => {
    void router.replace("/control");
  }, [router]);

  return null;
}
