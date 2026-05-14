import ReaderLayout from "@/components/reader/ReaderLayout";

export default function ReaderIndex() {
  return <ReaderLayout branchId={null} />;
}

export async function getServerSideProps() {
  return { props: {} };
}
