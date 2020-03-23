from typing import List, Callable
import json

from bs4 import BeautifulSoup

from .storage import ProxyPoolStorage
from .models import JobBase, CrawlJob, ValidateJob, ProxyItem

# JobFactory MetaClass
class JobFactoryMetaClass(type):
    def __new__(cls, name, classes, attrs):
        attrs["__Produce_Func__"]: List[callable] = list()
        for k, v in attrs.items():
            if k.startswith("produce_"):
                attrs["__Produce_Func__"].append(v)
        return type.__new__(cls, name, classes, attrs)

# JobFactory 基类
class JobFactory(object, metaclass=JobFactoryMetaClass):
    def get_jobs(self) -> List[JobBase]:
        job_list: List[JobBase] = list()
        for func in getattr(self, "__Produce_Func__"):
            job_list.extend(func(self))
        return job_list

# CrawlJob 工厂
class CrawlJobFactory(JobFactory):
    
    def __init__(self):
        self.storage = ProxyPoolStorage()
        self.page_count_for_xici = 1
    
    # 生产用户抓取 xicidaili 的 job
    def produce_job_for_xicidaili(self) -> List[CrawlJob]:
        # job callback
        def crawl_xici_job_callback(content: str):
            soup = BeautifulSoup(content, "lxml")
            for tr_node in soup.select("#ip_list tr")[1:]:
                td_node_list = tr_node.select("td")
                proxy_item = ProxyItem(
                    ip=td_node_list[1].string,
                    port=td_node_list[2].string,
                    https=td_node_list[5].string == "HTTPS"
                )
                self.storage.add(proxy_item)
        
        crawl_job_list: List[CrawlJob] = list()
        url_template = "https://www.xicidaili.com/nn/{}"
        for index in range(self.page_count_for_xici):
            target_url = url_template.format(index + 1)
            crawl_job_list.append(CrawlJob(target_url=target_url, callback=crawl_xici_job_callback))
        return crawl_job_list

# ValidateJob 工厂 
class ValidateJobFactory(JobFactory):

    def __init__(self):
        self.storage = ProxyPoolStorage()

    # 生产 ValidateJob
    def produce_validate_jobs(self) -> List[ValidateJob]:
        # job callback 
        def validate_job_callback(html_content: str, proxy_item: ProxyItem):
            # 验证响应是否有效
            is_valide = False
            try:
                if html_content != "":
                    json_dict = json.loads(html_content)
                    is_valide = json_dict.get("origin", "") == proxy_item.ip
            except ValueError:
                pass

            # 通知 Storage
            if is_valide: self.storage.activate(proxy_item)
            else: self.storage.deactivate(proxy_item)
        
        validate_jobs: List[ValidateJob] = list()
        for proxy in self.storage.get_all():
            validate_jobs.append(ValidateJob(proxy_item=proxy, callback=validate_job_callback))
        return validate_jobs
