import { useRouter } from "next/router";
import StudioLayout from "@/components/writer/StudioLayout";

export default function WriterBranch() {
  const router = useRouter();
  const branchId = typeof router.query.branchId === "string" ? router.query.branchId : null;
  return <StudioLayout branchId={branchId} />;
}

export async function getServerSideProps() {
  return { props: {} };
}
