from collections import Counter
import pynetbox
import requests
# from pynetbox import RequestError as APIRequestError

class NetBox:
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)
        
    def __init__(self, settings):
        self.counter = Counter(
            added=0,
            updated=0,
            manufacturer=0,
            module_added=0,
            module_port_added=0,
        )
        self.url = settings.NETBOX_URL
        self.token = settings.NETBOX_TOKEN
        self.handle = settings.handle
        self.netbox = None
        self.ignore_ssl = settings.IGNORE_SSL_ERRORS
        self.modules = False
        self.connect_api()
        self.verify_compatibility()
        self.existing_manufacturers = self.get_manufacturers()
        self.device_types = DeviceTypes(self.netbox, self.handle, self.counter)
        
    def connect_api(self):
        try:
            self.netbox = pynetbox.api(self.url, token=self.token)
            if self.ignore_ssl:
                self.handle.verbose_log("IGNORE_SSL_ERRORS is True, catching exception and disabling SSL verification.")
                requests.packages.urllib3.disable_warnings()
                self.netbox.http_session.verify = False
        except Exception as e:
            self.handle.exception("Exception", 'NetBox API Error', e)
            
    def get_api(self):
        return self.netbox
    
    def get_counter(self):
        return self.counter
    
    def verify_compatibility(self):
        # nb.version should be the version in the form '3.2'
        version_split = [int(x) for x in self.netbox.version.split('.')]

        # Later than 3.2
        # Might want to check for the module-types entry as well?
        if version_split[0] > 3 or (version_split[0] == 3 and version_split[1] >= 2):
            self.modules = True
            
    def get_manufacturers(self):
        return {str(item): item for item in self.netbox.dcim.manufacturers.all()}
            
    def create_manufacturers(self, vendors):
        to_create = []
        for vendor in vendors:
            try:
                manGet = self.existing_manufacturers[vendor["name"]]
                self.handle.verbose_log(f'Manufacturer Exists: {manGet.name} - {manGet.id}')
            except KeyError:
                to_create.append(vendor)
                self.handle.verbose_log(f"Manufacturer queued for addition: {vendor['name']}")
        
        if to_create:
            try:
                created_manufacturers = self.netbox.dcim.manufacturers.create(to_create)
                for manufacturer in created_manufacturers:
                    self.handle.verbose_log(f'Manufacturer Created: {manufacturer.name} - '
                        + f'{manufacturer.id}')
                    self.counter.update({'manufacturer': 1})
            except pynetbox.RequestError as request_error:
                self.handle.log("Error creating manufacturers")
                self.handle.verbose_log(f"Error during manufacturer creation. - {request_error.error}")
                
class DeviceTypes:
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)
        
    def __init__(self, netbox, handle, counter):
        self.netbox = netbox
        self.handle = handle
        self.counter = counter
        self.existing_device_types = self.get_device_types()
        
    def get_device_types(self):
        return {str(item): item for item in self.netbox.dcim.device_types.all()}
    
    def create_interfaces(self, interfaces, deviceType, nb):
        existing_interfaces = {str(item): item for item in nb.dcim.interface_templates.filter(devicetype_id=deviceType)}
        to_create = [interface for interface in interfaces if interface['name'] not in existing_interfaces]
        
        for interface in to_create:
            interface['device_type'] = deviceType

        if to_create:
            try:
                ifSuccess = nb.dcim.interface_templates.create(to_create)
                for intf in ifSuccess:
                    self.handle.verbose_log(f'Interface Template Created: {intf.name} - '
                    + f'{intf.type} - {intf.device_type.id} - '
                    + f'{intf.id}')
                    self.counter.update({'updated': 1})
            except pynetbox.RequestError as excep:
                self.handle.log(f"Error '{excep.error}' creating Interface")