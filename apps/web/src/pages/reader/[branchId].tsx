import { useRouter } from "next/router";
import ReaderLayout from "@/components/reader/ReaderLayout";

export default function ReaderBranch() {
  const router = useRouter();
  const branchId = typeof router.query.branchId === "string" ? router.query.branchId : null;
  return <ReaderLayout branchId={branchId} />;
}

export async function getServerSideProps() {
  return { props: {} };
}
