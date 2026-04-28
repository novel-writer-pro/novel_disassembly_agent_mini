import WorkbenchApp from "@/components/WorkbenchApp";

export default function ReaderRoute() {
  return <WorkbenchApp initialWorkspace="reader" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
