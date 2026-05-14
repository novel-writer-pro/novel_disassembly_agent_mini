import StudioLayout from "@/components/writer/StudioLayout";

export default function WriterIndex() {
  return <StudioLayout branchId={null} />;
}

export async function getServerSideProps() {
  return { props: {} };
}
