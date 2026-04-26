import "antd/dist/reset.css";
import "@/styles/globals.css";
import type { AppProps } from "next/app";
import { ConfigProvider, theme } from "antd";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#2872ff",
          colorBgBase: "#09111f",
          colorTextBase: "#eaf2ff",
          borderRadius: 14,
          fontSize: 14,
        },
        components: {
          Layout: {
            bodyBg: "#09111f",
            headerBg: "#101b2d",
            siderBg: "#0d1728",
          },
          Card: {
            colorBgContainer: "#101b2d",
          },
          Collapse: {
            colorBgContainer: "#0d1728",
          },
        },
      }}
    >
      <Component {...pageProps} />
    </ConfigProvider>
  );
}
